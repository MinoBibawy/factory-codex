"""Record proposal evidence and recheck its sources before implementing a follow-up."""
import argparse
import codecs
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

import factory


def digest(root, relative, *, document=False):
    """Anchor each lookup to an open directory; never follow a replaced link."""
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('..', '.git', '.factory') for p in path.parts):
        raise ValueError('Serve un file relativo al progetto, fuori dai metadati.')
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        directory = os.open(root, dir_flags)
        stack.callback(os.close, directory)
        for part in path.parts[:-1]:
            directory = os.open(part, dir_flags, dir_fd=directory)
            stack.callback(os.close, directory)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        stack.callback(os.close, fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('La fonte deve essere un file regolare.')
        decoder = codecs.getincrementaldecoder('utf-8')() if document else None
        has_text = False
        h = hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
                if decoder:
                    text = decoder.decode(block)
                    has_text = has_text or bool(text.strip())
        if decoder:
            decoder.decode(b'', final=True)
            if not has_text:
                raise ValueError('Il rapporto deve contenere testo UTF-8.')
        return h.hexdigest()


def report_digest(directory, job):
    return digest(directory, Path('artifacts') / job['id'] / 'analysis.md', document=True)


def source_digest(directory, job, source):
    # Git worktrees live inside the trusted queue; no-Git jobs use its parent.
    tree = Path(job['worktree'])
    if job['branch']:
        expected = directory / 'trees' / job['id']
        if expected != tree:
            raise ValueError('Worktree inatteso.')
        if Path(source).is_absolute() or '..' in Path(source).parts:
            raise ValueError('Serve un percorso relativo al worktree.')
        return digest(directory, tree.relative_to(directory) / source)
    if tree != directory.parent:
        raise ValueError('Cartella locale inattesa.')
    return digest(tree, source)


def clean_commit(directory, job):
    if not job['branch']:
        raise ValueError('La prova su commit richiede un worktree Git.')
    factory.ensure_checkout(job, directory)
    tree = job['worktree']
    if factory.git('status', '--porcelain', '--untracked-files=all', cwd=tree):
        raise ValueError('La prova su commit richiede un worktree pulito.')
    return factory.git('rev-parse', 'HEAD', cwd=tree)


def check_commit(directory, job, sha):
    if clean_commit(directory, job) != sha:
        raise ValueError('Indicare il commit completo attualmente verificato nel worktree del job.')


def require_cases(case, control):
    if not case.strip() or not control.strip() or case.strip() == control.strip():
        raise ValueError('Registrare prove distinte per il caso originale e il controllo vicino.')


def require_report(directory, job):
    receipt = job.get('proposal')
    if not receipt or report_digest(directory, job) != receipt['report_sha256']:
        raise ValueError('Registrare la prova sul rapporto corrente prima di chiudere la proposta.')
    for source, fingerprint in receipt['sources'].items():
        if source_digest(directory, job, source) != fingerprint:
            raise ValueError(f'Fonte cambiata: {source}. Riesaminare il rapporto.')
    if receipt['status'] == 'commit':
        check_commit(directory, job, receipt['sha'])


def record(directory, job, args):
    if not job['design_only']:
        raise ValueError('Registrare la proposta nel job di sola analisi o progettazione.')
    if args.status == 'pending':
        if not args.reason.strip() or args.case or args.control:
            raise ValueError('Indicare il limite della prova con --reason.')
    else:
        require_cases(args.case, args.control)
    if args.status == 'commit':
        check_commit(directory, job, args.sha)
    elif args.sha:
        raise ValueError('--sha si applica soltanto a una prova su commit.')
    external = sorted({v.strip() for v in args.external})
    if '' in external:
        raise ValueError('Indicare un riferimento esterno leggibile.')
    sources = {}
    for raw in args.source:
        name = str(Path(raw))
        if name == '.':
            raise ValueError('Indicare il percorso di un file.')
        sources[name] = source_digest(directory, job, name)
    receipt = dict(status=args.status, sha=args.sha, case=args.case.strip(),
                           control=args.control.strip(), reason=args.reason.strip(),
                           sources=sources, external=external, report_sha256=report_digest(directory, job))
    if job.get('proposal') == receipt:
        return False
    job['proposal'] = receipt
    return True


def outstanding(directory, parent, child):
    receipt = parent['proposal']
    baseline = {'report': receipt['report_sha256']}
    observed = {'report': report_digest(directory, parent)}
    if receipt['status'] == 'commit':
        baseline['commit'] = receipt['sha']
        observed['commit'] = clean_commit(directory, child)
    for source, saved in receipt['sources'].items():
        key = 'file:' + source
        baseline[key] = saved
        try:
            observed[key] = source_digest(directory, child, source)
        except FileNotFoundError:
            observed[key] = 'missing'
    for label in receipt['external']:
        observed['external:' + label] = 'manual'
    for key, check in child.get('proposal_checks', {}).get(parent['id'], {}).items():
        baseline[key] = check['observed']
    return {key: value for key, value in observed.items() if value != baseline.get(key)}


def parents_to_check(directory, jobs, job):
    parents = [jobs[key] for key in job['after'] if jobs[key].get('design_only') and jobs[key].get('proposal')]
    if parents and job['branch']:
        if job['stage'] == 'queued':
            raise ValueError('Assegnare il job prima di ricontrollare le fonti nel worktree.')
        factory.ensure_checkout(job, directory)
    return {parent['id']: outstanding(directory, parent, job) for parent in parents}


def require_current(directory, jobs, job):
    for key, changed in parents_to_check(directory, jobs, job).items():
        if changed:
            raise ValueError(f"Ricontrollare la proposta {key}: {', '.join(changed)}")


def recheck(directory, jobs, job, args):
    changed = parents_to_check(directory, jobs, job).get(args.parent)
    if changed is None:
        raise ValueError('La proposta indicata non è una dipendenza del job.')
    entry = dict(observed=args.observed, evidence=args.evidence.strip())
    if args.key == 'commit':
        require_cases(args.case, args.control)
        entry.update(case=args.case.strip(), control=args.control.strip())
    elif args.case or args.control:
        raise ValueError('Le controprove --case e --control si applicano alla chiave commit.')
    existing = job.get('proposal_checks', {}).get(args.parent, {}).get(args.key)
    if args.key not in changed and entry == existing:
        return False
    if not entry['evidence'] or changed.get(args.key) != args.observed:
        raise ValueError('Rileggere lo stato e indicare la prova sull’impronta richiesta.')
    checks = job.setdefault('proposal_checks', {}).setdefault(args.parent, {})
    checks[args.key] = entry
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    add = sub.add_parser('record')
    add.add_argument('id')
    add.add_argument('worker')
    add.add_argument('status', choices=('pending', 'fixture', 'commit'))
    add.add_argument('--source', action='append', default=[])
    add.add_argument('--external', action='append', default=[])
    for name in ('case', 'control', 'reason', 'sha'):
        add.add_argument('--' + name, default='')
    sub.add_parser('status').add_argument('id')
    check = sub.add_parser('recheck')
    for name in ('id', 'worker', 'parent', 'key'):
        check.add_argument(name)
    check.add_argument('--observed', required=True)
    check.add_argument('--evidence', required=True)
    check.add_argument('--case', default='')
    check.add_argument('--control', default='')
    args = parser.parse_args()
    with factory.locked() as (directory, data):
        jobs = data['jobs']
        job = jobs[args.id]
        if args.operation == 'status':
            result = {'parents': parents_to_check(directory, jobs, job)}
        else:
            if job['worker'] != args.worker or job['stage'] != 'design':
                raise ValueError('Servono il titolare e un lavoro attivo in progettazione.')
            if args.operation == 'record':
                updated = record(directory, job, args)
            else:
                updated = recheck(directory, jobs, job, args)
            if updated:
                factory.stamp(job)
                factory.save(directory, data)
            result = job
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f'Factory: {exc}')
