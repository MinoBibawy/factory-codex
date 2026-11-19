"""Coda locale condivisa dai worktree di un progetto. Eseguire dal progetto."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid
import webbrowser

import board

ACTIVE = {'design', 'build', 'checks', 'review'}
TERMINAL = {'ok', 'ko'}


def git(*args, cwd=None, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise ValueError(result.stderr.strip() or 'Operazione Git fallita')
    return result.stdout.strip() if result.returncode == 0 else None


def root_dir():
    cwd = Path.cwd()
    common = git('rev-parse', '--path-format=absolute', '--git-common-dir', check=False)
    if common:
        base = Path(common).resolve() / 'factory'
    else:
        for parent in (cwd, *cwd.parents):
            if (parent / '.git').exists():
                raise ValueError('Impossibile identificare il repository Git')
            if (parent / '.factory').exists():
                break
        else:
            parent = cwd
        base = parent / '.factory'
    if base.is_symlink():
        raise ValueError(f'Archivio simbolico inatteso: {base}')
    return base


def write_atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode='w', encoding='utf-8') as handle:
        tmp = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


@contextmanager
def locked():
    directory = root_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / 'queue.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        source = directory / 'queue.json'
        if source.is_symlink():
            raise ValueError('Archivio coda inatteso')
        if source.exists():
            data = json.loads(source.read_text(encoding='utf-8'))
        else:
            project = git('rev-parse', '--show-toplevel', check=False) or directory.parent
            data = {'project': Path(project).name, 'jobs': {}}
        yield directory, data


def save(directory, data):
    html = board.render(list(data['jobs'].values()), data['project'], directory)
    write_atomic(directory / 'queue.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    write_atomic(directory / 'dashboard.html', html)


def stamp(job):
    job['revision'] = job.get('revision', 0) + 1
    job['updated'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    job['history'].append({key: job[key] for key in ('stage', 'updated', 'note', 'worker')})


def capacity(jobs, job, stage, previous):
    others = [other for other in jobs.values() if other['id'] != job['id']]
    if not job['branch'] and stage not in TERMINAL:
        for other in others:
            phase = other['feedback_from'] if other['stage'] == 'feedback' else other['stage']
            if phase in {'build', 'checks', 'review', 'ready'}:
                raise ValueError(f"Cartella locale riservata al lavoro {other['id']} fino a OK o KO")
    if stage in ACTIVE and previous not in ACTIVE:
        limit = 3 if job['branch'] else 1
        if sum(other['stage'] in ACTIVE for other in others) >= limit:
            raise ValueError(f'{limit} lavori già attivi. Riprovare quando si libera un posto.')


def mutate(job_id, callback, *, context=False):
    with locked() as (directory, data):
        job = data['jobs'][job_id]
        before = job['stage']
        if context:
            callback(job, directory, data['jobs'])
        else:
            callback(job)
        capacity(data['jobs'], job, job['stage'], before)
        stamp(job)
        save(directory, data)
        return job


def get(job_id):
    with locked() as (_, data):
        return data['jobs'][job_id]


def add(args):
    key = args.id
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', key):
        raise ValueError('ID atteso: 1–64 lettere minuscole ASCII, cifre, trattini o underscore')
    if not args.title.strip():
        raise ValueError('Titolo vuoto')
    design_only = args.design_only or args.proposal
    dependencies = sorted(set(args.after))
    with locked() as (directory, data):
        jobs = data['jobs']
        if key in jobs:
            existing = jobs[key]
            original = (existing['title'], existing['intake'], existing['design_only'], existing['after'],
                        existing.get('base_ref', 'HEAD'), bool(existing.get('bug')), bool(existing.get('proposal_requested')))
            if original != (args.title, args.note, design_only, dependencies, args.base, args.bug, args.proposal):
                raise ValueError('ID già usato con altri dati. Se è lo stesso lavoro, riprenderlo con show/claim.')
            return existing
        if set(dependencies) - jobs.keys():
            raise ValueError('Registrare prima i lavori indicati in --after')
        is_git = directory.name != '.factory'
        base = ''
        if is_git:
            base = git('rev-parse', '--verify', '--end-of-options', args.base + '^{commit}',
                       check=args.base != 'HEAD') or ''
        elif args.base != 'HEAD':
            raise ValueError('--base richiede Git')
        start_dir = str(directory / 'trees' / key) if is_git else str(directory.parent)
        job = dict(id=key, title=args.title, stage='queued', note=args.note, intake=args.note,
                   base=base, base_ref=args.base, worktree=start_dir, branch='factory/' + key if is_git else '',
                   worker='', feedback_from=None, design_only=design_only, after=dependencies, history=[],
                   require_intake=True, require_reviewer_agent=True, bug=args.bug)
        if args.proposal:
            job['proposal_requested'] = True
        jobs[key] = job
        stamp(job)
        save(directory, data)
        return job


def ensure_checkout(job, directory):
    if not job['base']:
        return
    tree = directory / 'trees' / job['id']
    if tree.parent.is_symlink() or tree.is_symlink() or str(tree) != job['worktree']:
        raise ValueError('Percorso del worktree inatteso')
    if tree.exists():
        top = git('rev-parse', '--show-toplevel', cwd=tree, check=False)
        common = git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=tree, check=False)
        branch = git('branch', '--show-current', cwd=tree, check=False)
        if top and common and Path(top).resolve() == tree and Path(common).resolve() == directory.parent and branch == job['branch']:
            if job['stage'] != 'queued' or git('rev-parse', 'HEAD', cwd=tree) == job['base']:
                return
        raise ValueError(f'Ispezionare il worktree esistente prima del recupero: {tree}')
    if job['stage'] != 'queued':
        raise ValueError(f'Worktree mancante. Ripristinare il checkout esistente: {tree}')
    tree.parent.mkdir(mode=0o700, exist_ok=True)
    git('worktree', 'add', '--quiet', '-b', job['branch'], str(tree), job['base'])


def dependent_base(job, jobs, requested):
    ref = requested or job.get('base_ref', 'HEAD')
    source = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    revisions = [source]
    for key in job['after']:
        parent = jobs[key]
        if parent['design_only']:
            continue
        revision = parent.get('integrated') or parent.get('quality', {}).get('sha')
        if not revision:
            raise ValueError(f'Manca il commit verificato di {key}')
        revisions.append(revision)
    candidates = [source] if requested else revisions
    for candidate in candidates:
        if all(git('merge-base', '--is-ancestor', revision, candidate, check=False) is not None
               for revision in revisions):
            return candidate
    raise ValueError('Serve una base che comprenda i commit di tutte le dipendenze. '
                     'Ripetere claim con --base REF dopo la loro integrazione autorizzata.')


def claim(args):
    with locked() as (directory, data):
        jobs = data['jobs']
        job = jobs[args.id]
        if job['stage'] in TERMINAL:
            raise ValueError('Lavoro concluso')
        if not args.worker.strip():
            raise ValueError('Identificatore del worker vuoto')
        current = job['worker']
        if args.recover_from is not None and current != args.recover_from:
            raise ValueError('Il titolare è cambiato, rileggere lo stato')
        if current and current != args.worker and args.recover_from != current:
            raise ValueError(f'Lavoro già assegnato a {current}')
        waiting = [key for key in job['after'] if jobs[key]['stage'] != 'ok']
        if waiting:
            raise ValueError('In attesa di: ' + ', '.join(waiting))
        if args.base and (job['stage'] != 'queued' or not job['after'] or not job['branch']):
            raise ValueError('Usare --base al claim solo per lavori Git dipendenti ancora in coda')
        if job['stage'] == 'queued':
            if job['branch'] and job['after']:
                job['base'] = dependent_base(job, jobs, args.base)
            elif job['branch'] and not job['base']:
                job['base'] = git('rev-parse', '--verify', 'HEAD^{commit}', check=False)
                if not job['base']:
                    raise ValueError('Lavoro in coda. Serve un primo commit nel progetto per isolare il worktree.')
        stage = 'design' if job['stage'] == 'queued' else job['stage']
        capacity(jobs, job, stage, job['stage'])
        ensure_checkout(job, directory)
        if current == args.worker:
            return job
        job['worker'] = args.worker
        if job['stage'] == 'queued':
            job['stage'] = 'design'
        stamp(job)
        save(directory, data)
        return job


def record_integration(job, commit, target_ref):
    card = job.get('delivery', {})
    if (card.get('status') != 'confirmed' or card.get('action') != 'merge'
            or card.get('sha') != job['quality']['sha']):
        raise ValueError('Serve la conferma del merge per il commit verificato di questo lavoro')
    expected = f"{card['remote']}/{card['target']}"
    if target_ref != expected or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit or ''):
        raise ValueError(f'Indicare SHA integrale del commit integrato e --target-ref {expected}')
    if git('rev-parse', '--verify', commit + '^{commit}') != commit or commit == card['target_sha']:
        raise ValueError('Il commit integrato deve essere successivo alla base approvata')
    git('merge-base', '--is-ancestor', card['target_sha'], commit)
    git('merge-base', '--is-ancestor', commit, 'refs/remotes/' + expected)
    job.update(integrated=commit, integrated_target=expected)


def intake(args):
    review = dict(decision=args.decision, agent=args.agent.strip(),
                  skill=args.skill.strip(), evidence=args.evidence.strip())
    if not all(review.values()) or review['agent'] == args.worker.strip():
        raise ValueError('Servono un agente distinto dal titolare, la skill usata e il riscontro.')

    def record(job):
        if job['stage'] != 'design' or not job['worker'] or job['worker'] != args.worker:
            raise ValueError('Registrare la presa in carico con il titolare del lavoro in progettazione.')
        if job.get('bug') and not job['design_only'] and args.decision == 'accept':
            if not args.example or not args.example.strip() or not args.expected or not args.expected.strip():
                raise ValueError('Per accettare una fix servono --example e --expected dalla presa in carico.')
            review.update(example=args.example.strip(), expected=args.expected.strip())
        elif args.example is not None or args.expected is not None:
            raise ValueError('Registrare esempio e risultato atteso quando si accetta una fix da sviluppare.')
        reviews = job.setdefault('intake_reviews', [])
        if reviews and reviews[-1]['decision'] == 'accept':
            if reviews[-1] == review:
                return
            raise ValueError('Presa in carico già accettata per questo lavoro.')
        reviews.append(review)
        job['note'] = review['evidence']
        if args.decision == 'needs-info':
            job.update(stage='feedback', feedback_from='design')
        elif args.decision == 'reject':
            job['stage'] = 'ko'

    return mutate(args.id, record)


def ask_decision(job, key, question):
    if not key.strip() or not question.strip():
        raise ValueError('Servono una chiave stabile e una domanda.')
    decisions = job.setdefault('decisions', [])
    prior = next((item for item in decisions if item['key'] == key), None)
    if prior:
        if prior['question'] != question:
            raise ValueError('Chiave già associata a una domanda diversa.')
        return False
    if job['stage'] not in {'design', 'build'}:
        raise ValueError('Aprire la decisione durante analisi o sviluppo.')
    ref = uuid.uuid4().hex
    decisions.append(dict(key=key, ref=ref, question=question, from_stage=job['stage']))
    job.update(stage='feedback', feedback_from=job['stage'], decision_wait=ref, note=question)
    return True


def answer_decision(jobs, job, ref, answer):
    decisions = job.get('decisions') or []
    if not answer.strip() or not decisions or decisions[-1]['ref'] != ref:
        raise ValueError('Servono la risposta e il riferimento alla domanda corrente.')
    decision = decisions[-1]
    recorded = 'answer' in decision
    if recorded and decision['answer'] != answer:
        raise ValueError('Risposta già registrata con contenuto diverso.')
    if job.get('decision_wait') != ref:
        if recorded:
            return False
        raise ValueError('La domanda non è più aperta.')
    if job['stage'] != 'feedback' or job['feedback_from'] != decision['from_stage']:
        raise ValueError('Stato della domanda cambiato, rileggere il lavoro.')
    decision['answer'] = answer
    try:
        capacity(jobs, job, decision['from_stage'], 'feedback')
    except ValueError as error:
        # La risposta resta acquisita mentre un altro job occupa il posto.
        note = f"Risposta acquisita. {error}"
        changed = not recorded or job['note'] != note
        job['note'] = note
        return changed
    job.update(stage=decision['from_stage'], feedback_from=None, note=answer)
    del job['decision_wait']
    return True


def project_decision(args):
    with locked() as (directory, data):
        jobs = data['jobs']
        job = jobs[args.id]
        if not job.get('worker') or args.worker != job['worker']:
            raise ValueError('Serve il titolare attuale del lavoro.')
        if (job.get('delivery') or {}).get('status') == 'waiting':
            raise ValueError('Usare il flusso di approvazione della consegna.')
        if args.cmd == 'ask':
            changed = ask_decision(job, args.key.strip(), args.question.strip())
        else:
            changed = answer_decision(jobs, job, args.ref, args.answer.strip())
        if changed:
            stamp(job)
            save(directory, data)
        return job


def publication_step(job, sha):
    """Resolve the next local action against the approved, published revision."""
    receipt = job.get('ci') or {}
    delivery = job.get('delivery') or {}
    confirmed_push = delivery.get('action') == 'push' and delivery.get('status') == 'confirmed'
    if not receipt and not confirmed_push:
        return 'ready'
    if confirmed_push and sha != delivery.get('sha'):
        return 'push'
    if receipt and sha != receipt.get('sha'):
        return 'push'
    if confirmed_push and (receipt.get('push_receipt') != delivery.get('receipt') or
                           any(receipt.get(k) != delivery.get(k) for k in ('repo', 'branch'))):
        return 'ci'
    # Tornato a ready sullo stesso SHA, un errore di infrastruttura può essere stato risolto sul provider.
    return 'ready' if receipt.get('status') == 'pass' else 'ci'


def move(args):
    def advance(job, directory, jobs):
        old, target = job['stage'], args.stage
        if not job['worker'] or job['worker'] != args.worker or old in TERMINAL:
            raise ValueError('Verificare titolare e stato del lavoro')
        if target in {'feedback', 'ko'} and not args.note.strip():
            raise ValueError('Indicare la domanda o il motivo con --note')
        if old == 'feedback' and job.get('decision_wait'):
            if target != 'ko':
                raise ValueError('Registrare la risposta alla domanda con answer.')
            del job['decision_wait']
        if old == 'feedback' and target != 'ko':
            if job.get('delivery', {}).get('status') == 'waiting':
                raise ValueError('Usare il flusso di approvazione della consegna')
            allowed = {job['feedback_from']}
        elif old == 'design' and job['design_only']:
            allowed = {'ok', 'ko', 'feedback'}
        else:
            next_steps = {'design': {'build'}, 'build': {'checks'}, 'checks': {'build'},
                          'review': {'build'}, 'ready': {'ok', 'build'}}
            allowed = next_steps.get(old, set()) | {'ko', 'feedback'}
        if target not in allowed or target == old:
            raise ValueError(f'Passaggio manuale non consentito: {old} → {target}')
        if old == 'design' and target in {'build', 'ok'} and job.get('require_intake'):
            reviews = job.get('intake_reviews', [])
            if not reviews or reviews[-1]['decision'] != 'accept':
                raise ValueError('Serve la presa in carico accettata da un agente dedicato.')
        if old == 'design' and target == 'ok' and (job.get('proposal_requested') or job.get('proposal')):
            from proposal import require_report
            require_report(directory, job)
        if old == 'design' and target == 'build' and job.get('after'):
            from proposal import require_current
            require_current(directory, jobs, job)
        integration = args.integrated is not None or args.target_ref is not None
        if integration and (old, target) != ('ready', 'ok'):
            raise ValueError('Registrare il risultato del merge solo chiudendo il lavoro verificato')
        if old == 'ready' and target == 'ok':
            from quality import verify_job
            verify_job(job)
            if publication_step(job, job['quality']['sha']) != 'ready':
                raise ValueError('Per chiudere questa consegna occorre la CI superata sul commit pubblicato e approvato.')
            if integration:
                record_integration(job, args.integrated, args.target_ref)
        job['feedback_from'] = old if target == 'feedback' else None
        job['stage'], job['note'] = target, args.note
    return mutate(args.id, advance, context=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='cmd', required=True)
    new = commands.add_parser('add')
    new.add_argument('id')
    new.add_argument('title')
    new.add_argument('--note', default='')
    new.add_argument('--design-only', action='store_true')
    new.add_argument('--proposal', action='store_true', help='Proposta senza sviluppo, con rapporto e stato della verifica')
    new.add_argument('--bug', action='store_true', help='Fix che richiede la riprova del caso originale')
    new.add_argument('--require-intake', action='store_true', help='Compatibilità: già obbligatorio per i nuovi lavori')
    new.add_argument('--base', default='HEAD', help='Riferimento Git di partenza')
    new.add_argument('--after', action='append', default=[])
    commands.add_parser('list')
    commands.add_parser('show').add_argument('id')
    owner = commands.add_parser('claim')
    owner.add_argument('id')
    owner.add_argument('worker')
    owner.add_argument('--base', help='Base già integrata per un lavoro in coda con dipendenze')
    owner.add_argument('--recover-from', help='Titolare precedente, già verificato inattivo')
    triage = commands.add_parser('intake')
    triage.add_argument('id')
    triage.add_argument('worker')
    triage.add_argument('decision', choices=('accept', 'needs-info', 'reject'))
    triage.add_argument('--agent', required=True)
    triage.add_argument('--skill', required=True)
    triage.add_argument('--evidence', required=True)
    triage.add_argument('--example', help='Input o passi originali per riprodurre il problema')
    triage.add_argument('--expected', help='Risultato atteso in un formato direttamente confrontabile')
    ask = commands.add_parser('ask', help='Aprire una decisione di progetto')
    ask.add_argument('id')
    ask.add_argument('worker')
    ask.add_argument('key', help='Chiave stabile per questa domanda nel job')
    ask.add_argument('question')
    answer = commands.add_parser('answer', help='Rispondere a una specifica decisione')
    answer.add_argument('id')
    answer.add_argument('worker')
    answer.add_argument('ref', help='Riferimento univoco restituito da ask')
    answer.add_argument('answer')
    replay = commands.add_parser('replay')
    replay.add_argument('id')
    replay.add_argument('worker')
    replay.add_argument('--agent', required=True)
    replay.add_argument('--sha', required=True)
    replay.add_argument('--plan', required=True, help='Impronta del piano dei controlli verificato')
    replay.add_argument('--observed', required=True)
    replay.add_argument('--evidence', required=True)
    step = commands.add_parser('move')
    step.add_argument('id')
    step.add_argument('worker')
    step.add_argument('stage')
    step.add_argument('--note', default='')
    step.add_argument('--integrated', help='SHA restituito dal provider per la PR integrata')
    step.add_argument('--target-ref', help='REMOTE/TARGET aggiornato dopo il merge')
    dashboard = commands.add_parser('dashboard')
    dashboard.add_argument('--open', action='store_true', help='Mostra la dashboard nel browser predefinito')
    args = parser.parse_args()
    if args.cmd == 'add':
        result = add(args)
    elif args.cmd == 'claim':
        result = claim(args)
    elif args.cmd == 'intake':
        result = intake(args)
    elif args.cmd in {'ask', 'answer'}:
        result = project_decision(args)
    elif args.cmd == 'replay':
        from replay import record
        result = record(args)
    elif args.cmd == 'move':
        result = move(args)
    elif args.cmd == 'show':
        result = get(args.id)
    else:
        with locked() as (directory, data):
            result = list(data['jobs'].values())
            if args.cmd == 'dashboard':
                path = directory / 'dashboard.html'
                write_atomic(path, board.render(result, data['project'], directory))
        if args.cmd == 'dashboard':
            print(path, flush=True)
            if args.open and not webbrowser.open(path.as_uri()):
                raise ValueError('Apertura della dashboard non riuscita. Usa il percorso indicato.')
            return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        sys.exit(f'Factory: {error}')
