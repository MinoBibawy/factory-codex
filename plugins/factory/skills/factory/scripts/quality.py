"""Controlli locali del progetto e ricevute delle review sulla revisione verificata."""
import argparse
import fcntl
import hashlib
from itertools import chain
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import factory
import impact


RISKS = ['low', 'medium', 'high']
ROLES = ['code', 'security', 'quality', 'ui', 'ux', 'backend']
SURFACE = {'ui': 'ui', 'ux': 'ui', 'backend': 'backend'}
SKILLS = {'security': {'security-audit', 'factory-security-review'}, 'quality': {'ponytail-review', 'poteto-mode'}}
PLAN = 'checks.json'
CACHES = {'.factory', '.git', '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache',
          '.venv', 'node_modules'}


def git(tree, *args, allow_no_match=False):
    proc = subprocess.run(['git', '-C', str(tree), *args], capture_output=True)
    if proc.returncode and not (allow_no_match and proc.returncode == 1):
        raise ValueError(proc.stderr.decode(errors='replace').strip() or 'Controllo Git fallito')
    return os.fsdecode(proc.stdout)


def checked_plan(data):
    if not isinstance(data, dict) or set(data) - {'checks', 'protected', 'surfaces', 'layer_checks', 'impact_paths'}:
        raise ValueError('Piano non valido: sono ammessi checks, layer_checks, impact_paths, protected e surfaces')
    checks = data.get('checks')
    if not isinstance(checks, list) or not checks:
        raise ValueError('Occorre almeno un controllo del progetto')
    protected = data.get('protected', [])
    if not isinstance(protected, list) or not all(isinstance(s, str) and s.strip() and
            not Path(s).is_absolute() and '..' not in Path(s).parts and Path(s) != Path('.') for s in protected):
        raise ValueError('Percorsi protetti relativi al repository richiesti')
    surfaces = data.get('surfaces', [])
    if not isinstance(surfaces, list) or any(s not in ('ui', 'backend') for s in surfaces):
        raise ValueError('surfaces deve elencare i livelli presenti: ui, backend')
    layers = data.get('layer_checks', {})
    if not isinstance(layers, dict) or layers.keys() - set(surfaces):
        raise ValueError('Ogni gruppo layer_checks deve appartenere a una superficie dichiarata')
    for group in (checks, *layers.values()):
        if not isinstance(group, list) or not group:
            raise ValueError('Ogni gruppo deve contenere almeno un comando')
        for command in group:
            if not isinstance(command, list) or not command or not all(
                    isinstance(arg, str) and arg and '\x00' not in arg for arg in command):
                raise ValueError('Ogni controllo deve essere un elenco di argomenti')
    result = {'checks': checks, 'protected': sorted({str(Path(s)) for s in protected}),
              'surfaces': sorted(set(surfaces))}
    rules = data.get('impact_paths', {})
    if not isinstance(rules, dict) or rules.keys() - {'ui', 'backend', 'full'}:
        raise ValueError('impact_paths ammette i gruppi ui, backend e full')
    for patterns in rules.values():
        if not isinstance(patterns, list) or not patterns or not all(
                isinstance(p, str) and p.strip() and not Path(p).is_absolute()
                and '..' not in Path(p).parts and '\x00' not in p for p in patterns):
            raise ValueError('impact_paths richiede elenchi di pattern relativi al repository')
    if rules:
        result['impact_paths'] = rules
    if layers:
        result['layer_checks'] = layers
    return result


def commands_for(plan, receipt):
    commands = list(plan['checks'])
    for layer in ('ui', 'backend'):
        if receipt.get('small') and layer not in receipt['affected']:
            continue
        for command in plan.get('layer_checks', {}).get(layer, []):
            if command not in commands:
                commands.append(command)
    return commands


def local_hashes(tree, protected):
    content = hashlib.sha256()
    policy = hashlib.sha256()

    def unreadable(error):
        raise error

    for directory, dirs, files in os.walk(tree, onerror=unreadable):
        folder = Path(directory)
        dirs[:] = sorted(set(dirs) - CACHES)
        for name in list(dirs):
            if (folder / name).is_symlink():
                dirs.remove(name)
                files.append(name)
        for name in sorted(files):
            path = folder / name
            relative = str(path.relative_to(tree))
            mode = path.lstat().st_mode
            digest = hashlib.sha256()
            if stat.S_ISLNK(mode):
                digest.update(os.fsencode(os.readlink(path)))
            elif stat.S_ISREG(mode):
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(128 * 1024), b''):
                        digest.update(chunk)
            else:
                raise ValueError('File speciale nel progetto: ' + relative)
            entry = os.fsencode(relative) + b'\0' + str(mode).encode() + b'\0' + digest.digest()
            content.update(entry)
            if any(relative == p or relative.startswith(p + '/') for p in protected):
                policy.update(entry)
    return 'local:' + content.hexdigest(), policy.hexdigest()


def configure(source):
    root = factory.root_dir()
    trees = (root / 'trees').resolve()
    if Path.cwd().resolve().is_relative_to(trees) or source.resolve().is_relative_to(trees):
        raise ValueError('Configura i controlli dal progetto di origine, fuori dai worktree dei job')
    plan = checked_plan(json.loads(source.read_text()))
    if root.name == '.factory':
        plan['local_protected'] = local_hashes(root.parent, plan['protected'])[1]
    with factory.locked() as (directory, _):
        factory.write_atomic(directory / PLAN, json.dumps(plan, sort_keys=True))
    return plan


def read_plan():
    path = factory.root_dir() / PLAN
    if not path.is_file() or path.is_symlink():
        raise ValueError('Piano dei controlli assente: configura i controlli dal progetto di origine')
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Piano dei controlli non valido')
    local_baseline = data.pop('local_protected', None)
    return {**checked_plan(data), 'local_protected': local_baseline}, hashlib.sha256(raw).hexdigest()


def snapshot(job, plan, changed_paths=None):
    tree = job.get('worktree')
    root = factory.root_dir()
    if root.name == '.factory' and tree and Path(tree).resolve() == root.parent:
        fingerprint, protected = local_hashes(root.parent, plan['protected'])
        if protected != plan.get('local_protected'):
            raise ValueError('Il job ha modificato i percorsi protetti del progetto locale')
        return fingerprint
    if not tree or not job.get('branch') or not job.get('base'):
        raise ValueError('Serve un worktree Git dedicato per attestare il commit')
    if git(tree, 'branch', '--show-current').strip() != job['branch']:
        raise ValueError('Il branch del worktree è cambiato')
    if git(tree, 'status', '--porcelain=v1', '--untracked-files=all', '--ignore-submodules=none'):
        raise ValueError('Worktree non pulito: registra le modifiche da verificare')
    sha = git(tree, 'rev-parse', 'HEAD').strip()
    ancestor = git(tree, 'merge-base', job['base'], sha).strip()
    if ancestor != job['base']:
        raise ValueError('HEAD non discende dalla base registrata')
    names = git(tree, 'diff', '--name-only', '--no-renames', '-z', job['base'], sha, '--').split('\x00')
    if changed_paths is not None:
        changed_paths.extend(name for name in names if name)
    for name in names:
        if any(name == entry or name.startswith(entry + '/') for entry in plan['protected']):
            raise ValueError('Il job ha modificato un percorso protetto: ' + name)
    return sha


def valid_vote(role, vote, surfaces):
    if not vote.get('evidence', '').strip():
        return False
    if role in SKILLS and vote.get('skill') not in SKILLS[role]:
        return False
    if vote.get('decision') == 'na':
        return role in SURFACE and SURFACE[role] not in surfaces
    return vote.get('decision') == 'pass' and (role not in SURFACE or bool(vote.get('proof', '').strip()))


def answered(role, vote, surfaces):
    if vote.get('decision') == 'changes':
        return bool(vote.get('evidence', '').strip()) and (
            role not in SKILLS or vote.get('skill') in SKILLS[role])
    return valid_vote(role, vote, surfaces)


def required_roles(receipt):
    if (receipt.get('small') is True and receipt.get('risk') == 'low' and receipt.get('sensitive') is False
            and isinstance(receipt.get('affected'), list) and 'impact' in receipt):
        return [role for role in ROLES if role not in SURFACE or SURFACE[role] in receipt['affected']]
    return ROLES


def reviewed(receipt):
    roles = required_roles(receipt)
    if receipt.get('required') != roles:
        return False
    return all(valid_vote(r, receipt.get('votes', {}).get(r, {}), receipt['surfaces']) for r in roles)


def verify_reviews(job):
    if job['stage'] != 'ready' and not (job['stage'] == 'feedback' and job.get('feedback_from') == 'ready'):
        raise ValueError('Il lavoro deve completare tutti i controlli e le review')
    receipt = job.get('quality', {})
    plan, digest = read_plan()
    if job.get('findings') or not reviewed(receipt) or receipt.get('status') != 'pass' or receipt.get('plan') != digest:
        raise ValueError('Controlli o review mancanti o piano dei controlli cambiato')
    if snapshot(job, plan) != receipt.get('sha'):
        raise ValueError('Il commit è cambiato: ripetere controlli e review')


def verify_job(job):
    import replay
    verify_reviews(job)
    receipt = job['quality']
    replay.verify(job, receipt['sha'], receipt['plan'])


def fail(job, receipt, message):
    receipt['failures'] += 1
    job['note'] = message
    if receipt['failures'] >= 3:
        job.update(stage='feedback', feedback_from='build')
    else:
        job['stage'] = 'build'


def checks_lock_path(job_id):
    return factory.root_dir() / (hashlib.sha256(job_id.encode()).hexdigest() + '.checks.lock')


def check(job_id, risk, ui, backend, small=False, security=False):
    job = factory.get(job_id)
    with checks_lock_path(job_id).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Controlli già in corso per questo lavoro') from exc
        return run_checks(job_id, job, risk, ui, backend, lock.fileno(), small, security)


def run_checks(job_id, original, risk, ui, backend, lock_fd, small, security):
    if original['stage'] not in ('checks', 'review', 'ready'):
        raise ValueError('Avvia i controlli dopo lo sviluppo o per riverificare il risultato')
    plan, digest = read_plan()
    previous = original.get('quality', {})
    affected = set(previous.get('affected', previous.get('surfaces', [])))
    risk = max(previous.get('risk', 'low'), risk, key=RISKS.index)
    if ui:
        affected.add('ui')
    if backend:
        affected.add('backend')
    surfaces = affected | set(previous.get('surfaces', [])) | set(plan['surfaces'])
    sensitive = security or previous.get('sensitive', False)
    small = bool(small and risk == 'low' and not sensitive and not original.get('findings')
                 and (not previous or {'affected', 'small', 'sensitive'} <= previous.keys()))
    receipt = {'round': previous.get('round', 0) + 1, 'failures': previous.get('failures', 0),
               'risk': risk, 'surfaces': sorted(surfaces), 'affected': sorted(affected),
               'small': small, 'sensitive': sensitive,
               'votes': {}, 'plan': digest,
               'sha': None, 'status': 'running', 'checks': []}
    problem = ''
    try:
        names = []
        receipt['sha'] = snapshot(original, plan, names)
        if small:
            boundaries = set()
            # Interroga entrambi gli alberi: può cambiare il corpo di una rotta senza cambiare il decoratore.
            for start_index in range(0, len(names), 32):
                matches = git(original['worktree'], '--literal-pathspecs', 'grep', '--no-textconv', '-IilzE',
                              '-e', impact.BOUNDARY_LINES, original['base'], receipt['sha'], '--',
                              *names[start_index:start_index + 32], allow_no_match=True)
                boundaries.update(entry.partition(':')[2] for entry in matches.split('\x00') if entry)
            report = impact.assess(names, affected, plan.get('impact_paths', {}), bool(original.get('branch')), boundaries)
            receipt['impact'] = report
            affected.update(report['detected'])
            surfaces.update(affected)
            if report['reasons']:
                small, risk = False, 'medium'
            receipt.update(small=small, risk=risk, affected=sorted(affected), surfaces=sorted(surfaces))
    except (OSError, ValueError) as exc:
        problem = str(exc)
    receipt['required'] = required_roles(receipt)

    def start(job):
        if job['revision'] != original['revision']:
            raise ValueError('Il lavoro è cambiato prima del controllo')
        if previous:
            job.setdefault('quality_history', []).append(previous)
            # I verdetti precedenti all'introduzione dei rilievi identificavano solo il ruolo.
            for role, vote in previous.get('votes', {}).items():
                if vote['decision'] == 'changes':
                    job.setdefault('findings', {}).setdefault(role, {
                        'agent': vote.get('agent', role), 'evidence': vote['evidence'],
                        'sha': previous['sha'], 'proofs': [vote['proof']] if vote.get('proof') else []})
        job.update(stage='checks', quality=receipt, note='Controlli in corso')

    active = factory.mutate(job_id, start)
    try:
        if problem:
            raise ValueError(problem)
        for args in commands_for(plan, receipt):
            # Il comando mantiene il lock anche se il coordinatore viene interrotto.
            proc = subprocess.run(args, cwd=active['worktree'], stdout=sys.stderr, stderr=sys.stderr,
                                  check=False, pass_fds=(lock_fd,))
            receipt['checks'].append({'argv': args, 'exit': proc.returncode})
            if proc.returncode:
                raise ValueError(f'Controllo fallito ({proc.returncode}): {args[0]}')
        if receipt['sha'] != snapshot(active, plan):
            raise ValueError('Il commit è cambiato durante i controlli')
        if read_plan()[1] != digest:
            raise ValueError('Piano modificato durante i controlli')
    except (OSError, ValueError) as exc:
        problem = str(exc)

    def finish(job):
        if job['revision'] != active['revision'] or job['worker'] != active['worker'] or job['stage'] != 'checks':
            raise ValueError('Esito scaduto: il lavoro è cambiato durante i controlli')
        job['quality'] = receipt
        receipt['status'] = 'fail' if problem else 'pass'
        if problem:
            fail(job, receipt, problem)
            return
        # Un ricontrollo interrotto ha salvato il round certificato precedente nella cronologia.
        for prior in chain((previous,), reversed(original.get('quality_history', []))):
            if any(prior.get(k) != receipt[k] for k in ('required', 'plan', 'risk', 'surfaces')):
                break
            if (prior.get('small', False) != small or prior.get('sensitive', False) != sensitive
                    or prior.get('affected', prior.get('surfaces')) != receipt['affected']):
                break
            if prior.get('status') == 'running':
                continue
            if prior.get('status') == 'pass' and prior.get('sha') == receipt['sha']:
                receipt['votes'] = {r: v for r, v in prior['votes'].items() if answered(r, v, surfaces)}
            break
        job['stage'] = 'ready' if reviewed(receipt) else 'review'
        job['note'] = 'Pronto per la consegna' if job['stage'] == 'ready' else 'In attesa delle review richieste'

    result = factory.mutate(job_id, finish)
    if problem:
        raise ValueError(problem)
    return result


def current_review(job, role, sha, number):
    receipt = job.get('quality', {})
    if job['stage'] != 'review' or receipt.get('status') != 'pass' or role not in receipt.get('required', []):
        raise ValueError('Review non prevista o controlli ancora incompleti')
    plan, digest = read_plan()
    if receipt['round'] != number or receipt['plan'] != digest or sha != receipt['sha'] or sha != snapshot(job, plan):
        raise ValueError('Review superata dal commit, dal piano o dal round corrente')
    return receipt


def remedy(job_id, role, sha, number, proof):
    def record(job):
        receipt = current_review(job, role, sha, number)
        finding = job.get('findings', {}).get(role)
        if not finding or sha == finding['sha'] or not proof.strip():
            raise ValueError('Occorrono un rilievo aperto, una correzione su una nuova revisione e la prova eseguita')
        evidence = {'sha': sha, 'plan': receipt['plan'], 'proof': proof.strip()}
        previous = finding.get('remedy', {})
        if previous.get('sha') == sha and previous.get('plan') == receipt['plan'] and previous != evidence:
            raise ValueError('Una prova diversa è già registrata sulla stessa correzione')
        finding['remedy'] = evidence

    return factory.mutate(job_id, record)


def require_independent(job, agent):
    owners = {event['worker'].strip() for event in job.get('history', [])
              if event['stage'] == 'build'}
    owners.add(job['worker'].strip())
    if not agent or agent.strip() in owners or not agent.strip():
        raise ValueError('Indicare con --agent un revisore indipendente da chi ha sviluppato la modifica')


def handover(args):
    old, new, reason = (value.strip() for value in (args.from_agent, args.to_agent, args.reason))

    def record(job):
        receipt = current_review(job, args.role, args.sha, args.round)
        if job['worker'] != args.worker or not old or old == new or not reason:
            raise ValueError('Servono il titolare attuale, due revisori distinti e la verifica di indisponibilità')
        require_independent(job, new)
        finding = job.get('findings', {}).get(args.role)
        if not finding or args.role in receipt['votes']:
            raise ValueError('Il subentro richiede un rilievo aperto da riverificare in questo round')
        event = dict(role=args.role, from_agent=old, to_agent=new, reason=reason, worker=args.worker,
                     round=args.round, sha=args.sha, plan=receipt['plan'])
        history = job.setdefault('review_handovers', [])
        last = next((entry for entry in reversed(history) if entry['role'] == args.role), None)
        if finding['agent'] == new and last == event:
            return
        if finding['agent'] != old:
            raise ValueError('Il responsabile del rilievo è cambiato: rileggi le assegnazioni')
        finding['agent'] = new
        history.append(event)
        job['note'] = f'Subentro review {args.role}: {old} → {new}. {reason}'

    return factory.mutate(args.id, record)


def finding_decision(job, role, vote, receipt):
    findings = job.setdefault('findings', {})
    finding = findings.get(role)
    agent = vote.get('agent')
    if (finding or vote['decision'] == 'changes') and job.get('require_reviewer_agent'):
        require_independent(job, agent)
    if finding and (agent or role) != finding['agent']:
        raise ValueError('La controprova spetta al revisore assegnato al rilievo')
    fix = finding.get('remedy', {}) if finding else {}
    if (fix.get('sha'), fix.get('plan')) == (receipt['sha'], receipt['plan']):
        vote['remedy'] = fix
    if vote['decision'] == 'changes':
        scenarios = finding.get('scenarios', [finding['evidence']]) if finding else []
        proofs = finding['proofs'] if finding else []
        proof = vote.get('proof', '')
        previous_scenarios = {tuple(s.casefold().split()) for s in scenarios}
        known_scenario = tuple(vote['evidence'].casefold().split()) in previous_scenarios
        if known_scenario and (not proof or proof.casefold().split() in [p.casefold().split() for p in proofs]):
            vote['needs_feedback'] = True
        if not known_scenario:
            scenarios.append(vote['evidence'])
        if proof and proof not in proofs:
            proofs.append(proof)
        findings[role] = {'agent': agent or role, 'evidence': vote['evidence'], 'scenarios': scenarios,
                          'sha': receipt['sha'], 'proofs': proofs}
    elif finding:
        if vote['decision'] != 'pass' or not vote.get('proof') or 'remedy' not in vote:
            raise ValueError('Registrare la prova della correzione e la controprova del revisore assegnato')
        del findings[role]


def save_vote(job, receipt, agent, role, decision, evidence, skill=None, proof=None):
    if role not in receipt['required'] or decision not in ('pass', 'changes', 'na') or not evidence.strip():
        raise ValueError('Servono un ruolo previsto, un verdetto valido e una breve evidenza')
    vote = {'decision': decision, 'evidence': evidence.strip()}
    if agent and agent.strip():
        vote['agent'] = agent.strip()
    if role in SKILLS:
        if skill not in SKILLS[role]:
            raise ValueError(f'Per {role} indicare la skill usata: ' + ', '.join(sorted(SKILLS[role])))
        vote['skill'] = skill
    if proof:
        vote['proof'] = proof.strip()
    if decision != 'changes' and not valid_vote(role, vote, receipt['surfaces']):
        raise ValueError('PASS richiede la prova eseguita; NA è ammesso solo per un livello assente')
    old = receipt['votes'].get(role)
    if old and answered(role, old, receipt['surfaces']):
        original = {k: v for k, v in old.items() if k not in ('remedy', 'needs_feedback')}
        if original == vote:
            return
        raise ValueError('Esiste già un verdetto diverso per questo ruolo e round')
    if decision == 'pass':
        require_independent(job, agent)
    finding_decision(job, role, vote, receipt)
    if role in SURFACE and decision in ('changes', 'pass'):
        receipt['surfaces'] = sorted(set(receipt['surfaces']) | {SURFACE[role]})
    receipt['votes'][role] = vote


def verdicts(job_id, entries, sha, number, agent, *, grouped=False):
    if not isinstance(entries, list) or not 1 <= len(entries) <= len(ROLES):
        raise ValueError('Fornire un elenco non vuoto con un verdetto per ruolo')
    roles = []
    for entry in entries:
        required = {'role', 'decision', 'evidence'}
        if (not isinstance(entry, dict) or not required <= entry.keys()
                or entry.keys() - (required | {'proof', 'skill'})
                or not all(isinstance(value, str) for value in entry.values())):
            raise ValueError('Ogni verdetto richiede role, decision, evidence e può indicare skill e proof')
        if entry['role'] in roles:
            raise ValueError('Il rapporto contiene due verdetti per lo stesso ruolo')
        roles.append(entry['role'])

    def record(job):
        if grouped:
            require_independent(job, agent)
        receipt = current_review(job, roles[0], sha, number)
        for entry in entries:
            save_vote(job, receipt, agent, **entry)
        if grouped and any(not answered(role, receipt['votes'][role], receipt['surfaces']) for role in roles):
            raise ValueError('Gli esiti del rapporto sono discordanti sui livelli presenti')
        changes = [r for r, v in receipt['votes'].items() if v['decision'] == 'changes']
        pending = [r for r in receipt['required'] if not answered(r, receipt['votes'].get(r, {}), receipt['surfaces'])]
        if pending:
            job['note'] = 'Review in attesa: ' + ', '.join(pending)
        elif changes:
            receipt['status'] = 'changes'
            fail(job, receipt, 'Correzioni richieste: ' + ', '.join(changes))
            repeated = [r for r in changes if receipt['votes'][r].get('needs_feedback')]
            if repeated:
                job.update(stage='feedback', feedback_from='build',
                           note='Rilievo ripetuto senza una nuova prova: ' + ', '.join(repeated))
        else:
            job.update(stage='ready', note='Controlli e review superati')

    return factory.mutate(job_id, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest='action', required=True)
    cmds.add_parser('configure').add_argument('file', type=Path)
    checks = cmds.add_parser('check')
    checks.add_argument('id')
    checks.add_argument('--risk', choices=RISKS, required=True)
    checks.add_argument('--ui', action='store_true')
    checks.add_argument('--backend', action='store_true')
    checks.add_argument('--small', action='store_true', help='Cambiamento circoscritto ai livelli indicati')
    checks.add_argument('--security', action='store_true', help='Variazione sensibile: verifica completa')
    vote = cmds.add_parser('verdict')
    vote.add_argument('id')
    vote.add_argument('role', choices=ROLES)
    vote.add_argument('decision', choices=('pass', 'changes', 'na'))
    vote.add_argument('--sha', required=True)
    vote.add_argument('--round', type=int, required=True)
    vote.add_argument('--evidence', required=True)
    vote.add_argument('--proof', help='Prova effettivamente eseguita e risultato')
    vote.add_argument('--agent', help='Agente revisore che ha esaminato lo scenario')
    batch = cmds.add_parser('verdicts')
    batch.add_argument('id')
    batch.add_argument('report', type=Path)
    batch.add_argument('--sha', required=True)
    batch.add_argument('--round', type=int, required=True)
    batch.add_argument('--agent', required=True)
    transfer = cmds.add_parser('handover')
    transfer.add_argument('id')
    transfer.add_argument('role', choices=ROLES)
    transfer.add_argument('--worker', required=True)
    transfer.add_argument('--from-agent', required=True)
    transfer.add_argument('--to-agent', required=True)
    transfer.add_argument('--reason', required=True, help='Riscontro della verifica di indisponibilità')
    transfer.add_argument('--sha', required=True)
    transfer.add_argument('--round', type=int, required=True)
    fix = cmds.add_parser('remedy')
    fix.add_argument('id')
    fix.add_argument('role', choices=ROLES)
    fix.add_argument('--sha', required=True)
    fix.add_argument('--round', type=int, required=True)
    fix.add_argument('--proof', required=True)
    vote.add_argument('--skill', help='Skill specialistica effettivamente usata')
    cmds.add_parser('verify').add_argument('id')
    args = parser.parse_args()
    if args.action == 'configure':
        result = configure(args.file)
    elif args.action == 'check':
        result = check(args.id, args.risk, args.ui, args.backend, args.small, args.security)
    elif args.action == 'handover':
        result = handover(args)
    elif args.action == 'remedy':
        result = remedy(args.id, args.role, args.sha, args.round, args.proof)
    elif args.action == 'verdict':
        entry = dict(role=args.role, decision=args.decision, evidence=args.evidence)
        if args.skill:
            entry['skill'] = args.skill
        if args.proof:
            entry['proof'] = args.proof
        result = verdicts(args.id, [entry], args.sha, args.round, args.agent)
    elif args.action == 'verdicts':
        entries = json.loads(args.report.read_text(encoding='utf-8'))
        result = verdicts(args.id, entries, args.sha, args.round, args.agent, grouped=True)
    else:
        job = factory.get(args.id)
        verify_job(job)
        result = {'id': args.id, 'sha': job['quality']['sha'], 'status': 'pass'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, ValueError, OSError) as error:
        sys.exit(str(error))
