"""Riprova del caso originale, affidata all'agente che lo ha preso in carico."""
import factory
import quality


def case_for(job):
    intake = job.get('intake_reviews', [])
    if not intake or intake[-1].get('decision') != 'accept' or not all(
            intake[-1].get(key) for key in ('agent', 'example', 'expected')):
        raise ValueError('Mancano esempio, atteso o agente nella presa in carico della fix.')
    return intake[-1]


def verify(job, sha, plan):
    if not job.get('bug') or job['design_only']:
        return
    case = case_for(job)
    attempts = job.get('replays', [])
    if attempts:
        last = attempts[-1]
        if (last.get('matched') is True and last.get('sha') == sha and last.get('plan') == plan
                and last.get('agent') == case['agent'] and last.get('observed') == case['expected']
                and last.get('evidence', '').strip()):
            return
    raise ValueError('Serve la riprova del caso originale da parte della presa in carico sulla revisione corrente.')


def record(args):
    def apply(job):
        if job['stage'] != 'ready':
            raise ValueError('Concludere le review prima della riprova del caso originale.')
        if job['worker'] != args.worker or not job.get('bug') or job['design_only']:
            raise ValueError('Registrare la riprova con il titolare di una fix sviluppata.')
        case = case_for(job)
        if args.agent.strip() != case['agent']:
            raise ValueError('La riprova spetta allo stesso agente della presa in carico.')
        observed, evidence = args.observed.strip(), args.evidence.strip()
        if not observed or not evidence:
            raise ValueError('Indicare risultato osservato e prova eseguita.')
        quality.verify_reviews(job)
        receipt = job['quality']
        if (args.sha, args.plan) != (receipt['sha'], receipt['plan']):
            raise ValueError('Riprova superata da una nuova revisione o configurazione.')
        matched = observed == case['expected']
        attempt = dict(sha=args.sha, plan=args.plan, agent=case['agent'], observed=observed,
                       evidence=evidence, matched=matched)
        attempts = job.setdefault('replays', [])
        if matched:
            if not attempts or attempts[-1] != attempt:
                attempts.append(attempt)
            job['note'] = 'Caso originale confermato dalla presa in carico. Pronto per la consegna.'
            return
        repeated = any(not old['matched'] and old['observed'] == observed and old['evidence'] == evidence
                       for old in attempts)
        attempts.append(attempt)
        note = f"Caso originale: {case['example']}. Atteso: {case['expected']}. Osservato: {observed}. Prova: {evidence}"
        quality.fail(job, receipt, note)
        if repeated:
            job.update(stage='feedback', feedback_from='build', note='Riprova ripetuta senza nuovi riscontri. ' + note)

    return factory.mutate(args.id, apply)
