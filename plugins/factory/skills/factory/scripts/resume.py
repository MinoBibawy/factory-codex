"""Individua i revisori da riprendere per un lavoro della factory."""
import argparse
import fcntl
import json
import sys

import factory
import quality
import replay


def assignments(job, missing, economy_model):
    receipt = job['quality']
    findings = job.get('findings', {})
    grouped = (receipt.get('risk') == 'low' and 'affected' in receipt
               and not receipt.get('sensitive') and not findings)
    economy = economy_model if grouped and receipt.get('small') else None
    groups = {}
    for role in missing:
        surface = quality.SURFACE.get(role)
        agent = findings.get(role, {}).get('agent')
        if agent:
            reviewer = 'origin'
        elif not grouped:
            reviewer = role
        elif surface in receipt['affected']:
            reviewer = 'frontend' if surface == 'ui' else 'backend'
        elif role == 'security' and economy and not receipt['affected']:
            reviewer = 'security'
        else:
            reviewer = 'general'
        groups.setdefault((reviewer, agent), []).append(role)

    result = []
    for (reviewer, agent), roles in groups.items():
        assignment = dict(reviewer=reviewer, agent=agent, roles=roles, model='inherit')
        if economy and 'security' not in roles:
            assignment.update(model=economy, effort='low')
        result.append(assignment)
    return result


def reconcile(job, economy_model=None):
    stage = job['stage']
    receipt = job.get('quality', {})
    result = dict(id=job['id'], stage=stage, action=stage, round=receipt.get('round'),
                  sha=receipt.get('sha'), plan=receipt.get('plan'), completed=[], missing=[], assignments=[])
    if stage == 'checks':
        try:
            with quality.checks_lock_path(job['id']).open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return {**result, 'action': 'wait_checks'}
        except FileNotFoundError:
            pass
        return {**result, 'action': 'check'}
    if stage not in ('review', 'ready'):
        return result
    try:
        plan, digest = quality.read_plan()
        sha = quality.snapshot(job, plan)
    except (ValueError, OSError) as error:
        return {**result, 'action': 'blocked', 'reason': str(error)}
    if (sha != receipt.get('sha') or digest != receipt.get('plan') or
            receipt.get('status') != 'pass' or receipt.get('required') != quality.required_roles(receipt)):
        return {**result, 'action': 'check', 'reason': 'Ripetere i controlli sulla revisione e sul piano correnti.'}
    for role in receipt['required']:
        vote = receipt.get('votes', {}).get(role, {})
        answered = quality.answered(role, vote, receipt['surfaces'])
        result['completed' if answered else 'missing'].append(role)
    if stage == 'review':
        result['assignments'] = assignments(job, result['missing'], economy_model)
    if stage == 'ready':
        try:
            replay.verify(job, sha, digest)
        except ValueError as error:
            return {**result, 'action': 'replay', 'reason': str(error)}
        result['action'] = factory.publication_step(job, sha)
        if result['action'] == 'ci':
            result['reason'] = (job.get('ci') or {}).get('detail') or 'Verificare il push e i controlli remoti.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('id')
    parser.add_argument('--economy-model', metavar='MODELLO',
                        help='Modello economico effettivamente disponibile per la delega nativa')
    args = parser.parse_args()
    with factory.locked() as (_, data):
        result = reconcile(data['jobs'][args.id], args.economy_model)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, ValueError, OSError) as error:
        sys.exit(f'Factory: {error}')
