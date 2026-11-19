"""Osserva i controlli del provider per il solo commit pubblicato con consenso."""
from datetime import datetime, timezone
import json
import re
import subprocess
from urllib.parse import quote

import delivery
import factory


def receipt(card):
    return dict(status='awaiting_push', repo=card['repo'], remote=card['remote'], branch=card['branch'],
                target=card['target'], sha=card['sha'], push_receipt=card['receipt'],
                detail='In attesa della verifica del ramo remoto.', checks=[])


def gh(host, *args):
    try:
        result = subprocess.run(['gh', 'api', '--hostname', host, *args], capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('GitHub CLI non disponibile o lettura scaduta.') from exc
    if result.returncode:
        raise ValueError('Impossibile leggere controlli e regole dal provider con GitHub CLI.')
    return json.loads(result.stdout)


QUERY = """
query($owner:String!,$name:String!,$sha:String!,$ref:String!,$endCursor:String) {
  repository(owner:$owner,name:$name) {
    url ref(qualifiedName:$ref) {name branchProtectionRule {
      requiresStatusChecks requiredStatusChecks {context app {databaseId}}
    }}
    object(expression:$sha) { ... on Commit {oid statusCheckRollup {state contexts(first:100,after:$endCursor) {
      totalCount pageInfo {hasNextPage endCursor} nodes {
        ... on CheckRun {id name status conclusion checkSuite {app {databaseId}}}
        ... on StatusContext {id context state}
      }
    }}}}
  }
}
"""


def github(card):
    parts = card['repo'].split('/')
    if len(parts) != 3 or not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', s) for s in parts):
        raise ValueError('Per questo provider occorre una lettura CI dal connettore con --ci-json.')
    host, owner, name = parts
    # Il ramo può includere slash e Unicode.
    path = f'repos/{owner}/{name}/rules/branches/{quote(card["target"], safe="")}?per_page=100'
    rules_pages = gh(host, '--paginate', '--slurp', path)
    required = []
    if not isinstance(rules_pages, list) or not rules_pages:
        raise ValueError('Regole di protezione del ramo non disponibili.')
    for page in rules_pages:
        if not isinstance(page, list):
            raise ValueError('Regole applicabili al ramo non verificabili.')
        for rule in page:
            if rule['type'] == 'required_status_checks':
                for check in rule['parameters']['required_status_checks']:
                    required.append(dict(name=check['context'], app=check.get('integration_id')))
            elif rule['type'] == 'workflows':
                raise ValueError('Verificare i workflow obbligatori del ruleset tramite il connettore CI.')
    pages = gh(host, '--paginate', '--slurp', 'graphql', '-f', 'query=' + QUERY, '-f', 'owner=' + owner,
               '-f', 'name=' + name, '-f', 'sha=' + card['sha'], '-f', 'ref=refs/heads/' + card['target'])
    if not isinstance(pages, list) or not pages:
        raise ValueError('Nessuna risposta sulla CI del commit.')
    checks, ids = [], set()
    for page in pages:
        repo = page['data']['repository']
        commit = repo['object']
        if (page.get('errors') or delivery.repo_name(repo['url']).casefold() != card['repo'].casefold()
                or commit['oid'] != card['sha'] or repo['ref']['name'] != card['target']):
            raise ValueError('La risposta GitHub non corrisponde al repository, al ramo e allo SHA.')
        protection = repo['ref']['branchProtectionRule']
        if protection and protection['requiresStatusChecks']:
            for check in protection['requiredStatusChecks']:
                app = check['app']
                if app is not None and (type(app.get('databaseId')) is not int or app['databaseId'] <= 0):
                    raise ValueError('Impossibile identificare la GitHub App richiesta dalla protezione del ramo.')
                required.append(dict(name=check['context'], app=app['databaseId'] if app else None))
        rollup = commit['statusCheckRollup']
        if rollup is None:
            total, overall = 0, 'PENDING'
            continue
        contexts = rollup['contexts']
        total, overall = contexts['totalCount'], rollup['state']
        for run in contexts['nodes']:
            if run['id'] in ids:
                raise ValueError('I controlli sono cambiati durante la lettura delle pagine.')
            ids.add(run['id'])
            if 'name' in run:
                context = run['name']
                outcome = run['conclusion'] if run['status'] == 'COMPLETED' else 'PENDING'
                app = ((run['checkSuite'] or {}).get('app') or {}).get('databaseId')
            else:
                context, outcome, app = run['context'], run['state'], None
            if outcome in ('SUCCESS', 'NEUTRAL', 'SKIPPED'):
                state = 'pass' if outcome == 'SUCCESS' else 'skipped'
            elif outcome in ('ERROR', 'FAILURE', 'TIMED_OUT', 'CANCELLED', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'STALE'):
                state = 'fail'
            else:
                state = 'pending'
            checks.append(dict(name=context, app=app, state=state))
    if total != len(checks):
        raise ValueError('Elenco dei controlli incompleto o cambiato durante la lettura.')
    if overall != 'SUCCESS' and checks and all(c['state'] in ('pass', 'skipped') for c in checks):
        checks.append(dict(name='Stato complessivo GitHub', state='pending'))
    return dict(repo=card['repo'], sha=card['sha'], target=card['target'], checks=checks,
                required=required, complete=True, observed_at=datetime.now(timezone.utc).isoformat())


def evaluate(card, data):
    if (not isinstance(data, dict) or any(data.get(k) != card[k] for k in ('repo', 'sha', 'target'))
            or data.get('complete') is not True):
        raise ValueError('La CI deve riferirsi esattamente a repository, ramo base e SHA e comprendere tutti i controlli.')
    stamp = datetime.fromisoformat(data['observed_at'])
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if not -10 <= age <= 120:
        raise ValueError('Rileggere la CI dal provider: osservazione scaduta.')
    checks, required = data['checks'], data['required']
    if not isinstance(checks, list) or not isinstance(required, list):
        raise ValueError('Servono controlli osservati e requisiti del ramo.')
    for check in checks + required:
        if (not isinstance(check, dict) or not isinstance(check.get('name'), str) or not check['name'].strip()
                or (check.get('app') is not None and type(check['app']) != int)):
            raise ValueError('Identità del controllo CI mancante o non valida.')
    if any(c.get('state') not in ('pass', 'pending', 'fail', 'skipped') for c in checks):
        raise ValueError('Esito CI sconosciuto.')
    checks = [{k:v for k,v in c.items() if k in ('name', 'state', 'app')} for c in checks]
    failed = [c['name'] for c in checks if c['state'] == 'fail']
    if failed:
        return 'fail', 'CI fallita: ' + ', '.join(failed), checks
    missing, skipped = [], []
    for expected in required:
        matches = [c for c in checks if c['name'] == expected['name'] and
                   (expected.get('app') in (None, -1) or expected['app'] == c.get('app'))]
        if not matches:
            missing.append(expected['name'])
        elif all(c['state'] == 'skipped' for c in matches):
            skipped.append(expected['name'])
    if skipped:
        return 'blocked', 'Controlli obbligatori saltati: ' + ', '.join(dict.fromkeys(skipped)), checks
    if missing:
        return 'pending', 'Controlli richiesti ancora assenti: ' + ', '.join(dict.fromkeys(missing)), checks
    if not checks:
        return 'pending', 'Nessun controllo pubblicato: verificare se la CI è configurata o deve ancora partire.', checks
    if any(c['state'] == 'pending' for c in checks):
        return 'pending', 'CI in attesa sul commit pubblicato.', checks
    if not any(c['state'] == 'pass' for c in checks):
        return 'blocked', 'Il provider riporta solo controlli saltati.', checks
    return 'pass', 'CI superata sul commit pubblicato.', checks


def published(job, card):
    git = lambda *args: delivery.git(job['worktree'], *args)
    remote = card['remote']
    if (delivery.repo_name(git('remote', 'get-url', remote)) != card['repo'] or
            [delivery.repo_name(u) for u in git('remote', 'get-url', '--all', '--push', remote).splitlines()] != [card['repo']]):
        raise ValueError('Repository remoto cambiato dopo il consenso al push.')
    ref = 'refs/heads/' + card['branch']
    return git('ls-remote', '--heads', remote, ref).split() == [card['sha'], ref]


def refresh(job, source=None):
    initial = job.get('ci')
    card = job.get('delivery', {})
    if not initial:
        if card.get('action') != 'push' or card.get('status') != 'confirmed' or not card.get('receipt'):
            raise ValueError('Manca un push confermato per avviare la CI.')
        initial = receipt(card)
    merge_waiting = (job['stage'] == 'feedback' and card.get('status') == 'waiting' and card.get('action') == 'merge')
    if (job['stage'] != 'ready' and not merge_waiting
            or card.get('action') == 'merge' and card.get('status') == 'confirmed'
            or job.get('quality', {}).get('sha') != initial['sha']
            or delivery.git(job['worktree'], 'rev-parse', 'HEAD') != initial['sha']):
        raise ValueError('La CI richiede il lavoro pronto sul commit del push confermato.')
    if initial['status'] == 'fail':
        from quality import verify_job
        verify_job(job)
    try:
        if not published(job, initial):
            status = 'awaiting_push' if initial['status'] == 'awaiting_push' else 'blocked'
            detail, checks = 'Il ramo remoto non punta al commit approvato.', []
        else:
            data = json.loads(source.read_text(encoding='utf-8')) if source else github(initial)
            status, detail, checks = evaluate(initial, data)
            if merge_waiting and source and datetime.fromisoformat(data['observed_at']) <= datetime.fromisoformat(card['requested_at']):
                raise ValueError('Ripetere la lettura dal provider dopo la richiesta di approvazione merge.')
            if not published(job, initial):
                raise ValueError('Il ramo remoto è cambiato durante la lettura CI.')
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as error:
        status, detail, checks = 'blocked', 'CI non verificabile. ' + str(error), []
    new = {**initial, 'status': status, 'detail': detail, 'checks': checks}
    with factory.locked() as (directory, state):
        current = state['jobs'][job['id']]
        if current['revision'] != job['revision']:
            raise ValueError('Lavoro cambiato durante la lettura CI. Rileggere lo stato.')
        if current.get('ci') == new and status != 'fail' and not (merge_waiting and status != 'pass'):
            return current
        current['ci'] = new
        if merge_waiting and status != 'pass':
            current['delivery']['status'] = 'cancelled'
            current.update(stage='ready', feedback_from=None)
        if status == 'fail':
            try:
                factory.capacity(state['jobs'], current, 'build', current['stage'])
                current.update(stage='build', feedback_from=None)
            except ValueError:
                current.update(stage='feedback', feedback_from='build')
                detail += ' Riprendere lo sviluppo appena si libera una corsia.'
        if not (merge_waiting and status == 'pass'):
            current['note'] = detail
        factory.stamp(current)
        factory.save(directory, state)
        return current


def require_pass(job, card):
    ci = job.get('ci') or {}
    if ci.get('status') != 'pass' or not ci.get('push_receipt') or any(ci.get(k) != card[k] for k in
            ('repo', 'remote', 'branch', 'target', 'sha')):
        raise ValueError('Serve la CI superata sullo stesso push, repository, branch, destinazione e commit.')
