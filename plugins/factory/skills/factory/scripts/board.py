"""Render the offline dashboard from the project's saved jobs."""

from datetime import datetime
from html import escape
from os import fsencode
import re
from shlex import join
from urllib.parse import quote_from_bytes

from delivery import valid_pr_url


GROUPS = {
    "attesa": ("Attende una risposta", "Nessuna richiesta in attesa."),
    "in-corso": ("In corso", "Nessun lavoro in corso."),
    "in-coda": ("In coda", "La coda è vuota."),
    "conclusi": ("Conclusi", "Nessun lavoro concluso."),
}
STAGES = {
    "queued": ("in-coda", "In coda"),
    "design": ("in-corso", "Progettazione"),
    "build": ("in-corso", "Sviluppo"),
    "checks": ("in-corso", "Controlli"),
    "review": ("in-corso", "Revisione"),
    "ready": ("in-corso", "Pronto per la consegna"),
    "feedback": ("attesa", "Feedback richiesto"),
    "ok": ("conclusi", "OK"),
    "ko": ("conclusi", "KO"),
}


def text(value):
    return escape(str(value))


def elapsed(events):
    if len(events) < 2:
        return ""
    first, last = (datetime.fromisoformat(e["updated"]) for e in (events[0], events[-1]))
    seconds = max(0, int((last - first).total_seconds()))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return " ".join(f"{n} {unit}" for n, unit in ((hours, "h"), (minutes, "min"), (seconds, "s")) if n) or "0 s"


def timeline(events):
    if not events:
        return ""
    items = []
    for event in reversed(events):
        stamp = event["updated"]
        label = STAGES[event["stage"]][1]
        items.append(f'<li><strong>{text(label)}</strong> <time datetime="{text(stamp)}">'
                     f'{text(stamp)}</time><p>{text(event.get("note", ""))}</p></li>')
    return '<h4>Cronologia</h4><ol class="timeline">' + "".join(items) + "</ol>"


def quality_rounds(job):
    rounds = {r["round"]: r for r in job.get("quality_history", [])}
    current = job.get("quality")
    if current:
        rounds[current["round"]] = current
    result = []
    for number in sorted(rounds, reverse=True):
        receipt = rounds[number]
        status = {"pass": "Controlli superati", "running": "Controlli in corso", "fail": "Controllo fallito",
                  "changes": "Modifiche richieste"}.get(receipt.get("status"), "Esito da registrare")
        result.append(f'<h4>Round {text(number)}</h4><p>{status}</p>')
        reasons = receipt.get("impact", {}).get("reasons", [])
        if reasons:
            items = "".join(f"<li>{text(reason)}</li>" for reason in reasons)
            result.append(f"<h4>Verifiche ampliate per il diff</h4><ul>{items}</ul>")
        if receipt.get("checks"):
            result.append("<ul>")
            for check in receipt["checks"]:
                code = check["exit"]
                result.append(f'<li><code>{text(join(check["argv"]))}</code> · '
                              f'<strong>{"OK" if code == 0 else "KO"} · exit {text(code)}</strong></li>')
            result.append("</ul>")
        if receipt.get("required"):
            result.append('<dl class="votes">')
            missing = "In attesa" if receipt is current and receipt.get("status") in ("running", "pass") else "Nessun verdetto registrato"
            for role in receipt["required"]:
                vote = receipt.get("votes", {}).get(role, {})
                decision = {"pass": "Approvato", "changes": "Modifiche richieste",
                            "na": "Non applicabile"}.get(vote.get("decision"), missing)
                if vote.get("decision") == "na" and ("ui" if role == "ux" else role) in receipt.get("surfaces", []):
                    decision = "Da riesaminare"
                evidence = f'<p>{text(vote["evidence"])}</p>' if vote.get("evidence") else ""
                skill = f'<p>Skill · <code>{text(vote["skill"])}</code></p>' if vote.get("skill") else ""
                proof = f'<p>Prova · <code>{text(vote["proof"])}</code></p>' if vote.get("proof") else ""
                agent = f'<p>Revisore · <code>{text(vote["agent"])}</code></p>' if vote.get("agent") else ""
                remedy = vote.get("remedy", {}).get("proof")
                fix = f'<p>Verifica dello sviluppatore · <code>{text(remedy)}</code></p>' if remedy else ""
                result.append(f'<dt>Review {text(role)}</dt><dd>{decision}{agent}{skill}{evidence}{fix}{proof}</dd>')
            result.append("</dl>")
    return "".join(result)


def handover_history(job):
    changes = job.get("review_handovers", [])
    if not changes:
        return ""
    items = []
    for change in changes:
        items.append(f'<li>Review {text(change["role"])} · {text(change["from_agent"])} → '
                     f'{text(change["to_agent"])} · round {text(change["round"])} '
                     f'(<code>{text(change["sha"])}</code>)<p>{text(change["reason"])}</p></li>')
    return "<h4>Subentri dei revisori</h4><ul>" + "".join(items) + "</ul>"


def artifact_links(directory, job_id):
    if directory is None or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', job_id):
        return ""
    root = directory / "artifacts" / job_id
    try:
        if root.parent.is_symlink() or root.is_symlink() or not root.is_dir():
            return ""
        paths = sorted(root.rglob("*"))
    except OSError:
        return ""
    items = []
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file():
                continue
        except OSError:
            continue
        href = quote_from_bytes(fsencode(path.relative_to(directory)))
        label = fsencode(path.relative_to(root)).decode("utf-8", errors="replace")
        items.append(f'<li><a href="{href}">{text(label)}</a></li>')
    return '<h4>Artefatti</h4><ul>' + "".join(items) + '</ul>' if items else ""


def proposal_status(job):
    proof = job.get("proposal") or {}
    if not proof and not job.get("proposal_requested"):
        return ""
    label = "Proposta da verificare"
    if proof.get("case") and proof.get("control"):
        if proof.get("status") == "fixture":
            label = "Verificata su copia temporanea"
        elif proof.get("status") == "commit" and proof.get("sha"):
            label = f"Verificata sul commit {proof['sha']}"
    return f'<p class="note">{text(label)}</p>'


def job_card(job, label, directory):
    delivery = job.get("delivery") or {}
    pr = job.get("pull_request") or {}
    if delivery.get("action") == "merge" and delivery.get("status") in ("waiting", "confirmed", "cancelled"):
        number, repo = delivery.get("pr"), delivery.get("repo") or ""
        if (pr.get("repo"), pr.get("number")) != (repo, number):
            route = {"github.com": "pull", "gitlab.com": "-/merge_requests"}.get(repo.partition("/")[0])
            pr = {"repo": repo, "number": number, "url": f"https://{repo}/{route}/{number}" if route else ""}
    pr_link = ""
    if valid_pr_url(pr.get("repo"), pr.get("number"), pr.get("url")):
        pr_link = f'<p class="pr"><a href="{text(pr["url"])}">PR/MR #{text(pr["number"])}</a></p>'
    note = job.get("note")
    stage = job["stage"]
    events = job.get("history", [])
    intake = job.get("intake_reviews", [])
    if stage == "design" and job.get("require_intake") and (not intake or intake[-1]["decision"] != "accept"):
        label = "Presa in carico"
    decisions = job.get("decisions", [])
    if stage == "feedback" and delivery.get("status") == "waiting":
        label = {"push": "Approvazione push", "merge": "Approvazione merge"}.get(delivery.get("action"), label)
    elif stage == "feedback" and job.get("decision_wait"):
        current = next((d for d in reversed(decisions) if d["ref"] == job["decision_wait"]), None)
        if current:
            label = "Risposta ricevuta" if current.get("answer") else "Decisione richiesta"
            if not current.get("answer"):
                note = current["question"]
    fields = [
        ("Dipende da", ", ".join(job.get("after", []))),
        ("Repository", delivery.get("repo")), ("Branch", job.get("branch")),
        ("Branch base della PR", delivery.get("target")), ("Commit proposto", delivery.get("sha")),
        ("Commit di partenza", job.get("base")), ("Worktree", job.get("worktree")),
        ("Rischio", {"low":"basso", "medium":"medio", "high":"alto"}.get((job.get("quality") or {}).get("risk"))),
        ("Intervallo tra primo e ultimo evento", elapsed(events)),
        ("Aggiornamento", job.get("updated")),
    ]
    proposal = job.get("proposal") or {}
    fields.extend([("Prova del caso originale", proposal.get("case")),
                   ("Prova di controllo", proposal.get("control")), ("Limiti della prova", proposal.get("reason"))])
    for decision in decisions:
        fields.extend([("Domanda", decision["question"]), ("Risposta", decision.get("answer"))])
    ci = job.get("ci")
    if ci:
        ci_label = {"awaiting_push": "Verifica del push", "pending": "CI in corso", "pass": "CI superata",
                    "fail": "CI fallita", "blocked": "CI da verificare"}.get(ci.get("status"), "CI da verificare")
        if stage == "ready" and ci.get("status") != "pass" and ci.get("sha") == (job.get("quality") or ci).get("sha"):
            label = ci_label
        fields.extend([("CI remota", ci_label), ("Commit CI", ci.get("sha")), ("Esito CI", ci.get("detail"))])
        fields.extend(("Controllo CI", f"{check['name']} · {check['state']}") for check in ci.get("checks", []))
    if intake:
        last = intake[-1]
        outcomes = {"accept": "Accettato", "needs-info": "Chiarimento richiesto", "reject": "Respinto"}
        fields.extend([("Agente di presa in carico", last["agent"]), ("Skill utilizzata", last["skill"]),
                       ("Decisione", outcomes[last["decision"]]), ("Evidenza", last["evidence"])])
    if job.get("bug") and not job.get("design_only") and intake:
        fields.extend([("Caso originale", last.get("example")), ("Risultato atteso", last.get("expected"))])
        checks = job.get("quality") or {}
        replays = job.get("replays") or []
        latest = replays[-1] if replays else {}
        if stage == "ready" and not (latest.get("matched") and latest.get("sha") == checks.get("sha")
                                     and latest.get("plan") == checks.get("plan")):
            label = "Verifica del caso originale"
            note = "L’agente di presa in carico deve riprovare il caso su questa revisione."
        if latest:
            fields.extend([("Ultima riprova", latest.get("observed")), ("Prova", latest.get("evidence")),
                           ("Revisione della riprova", latest.get("sha"))])
    rows = "".join(f"<dt>{key}</dt><dd>{text(value)}</dd>" for key, value in fields if value)
    body = artifact_links(directory, job["id"]) + (f"<dl>{rows}</dl>" if rows else "") + quality_rounds(job) + handover_history(job) + timeline(events)
    details = (f'<details><summary id="job-{text(job["id"])}">Dettagli del lavoro</summary>{body}</details>'
               if body else "")
    message = f'<p class="note">{text(note)}</p>' if note else ""
    return (
        f'<article class="card {text(stage)}">'
        f'<div class="card-head"><span class="ticket">#{text(job["id"])}</span>'
        f'<span class="badge">{text(label)}</span></div>'
        f'<h3>{text(job["title"])}</h3>{pr_link}{proposal_status(job)}{message}{details}</article>'
    )


def render(jobs, project, directory=None):
    groups = {key: [] for key in GROUPS}
    for job in sorted(jobs, key=lambda item: str(item.get("updated", "")), reverse=True):
        group, label = STAGES[job["stage"]]
        ci = job.get("ci") or {}
        if job["stage"] == "ready" and ci.get("status") == "blocked" and ci.get("sha") == (job.get("quality") or ci).get("sha"):
            group = "attesa"
        groups[group].append(job_card(job, label, directory))
    counts = []
    sections = []
    for group, (label, empty) in GROUPS.items():
        count = len(groups[group])
        counts.append(f'<a id="nav-{group}" href="#{group}"><span>{label}</span><strong>{count}</strong></a>')
        cards = "".join(groups[group]) or f'<p class="empty">{empty}</p>'
        sections.append(
            f'<section id="{group}" aria-labelledby="heading-{group}">'
            f'<h2 id="heading-{group}">{label}</h2>{cards}</section>'
        )
    return f'''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Factory · {text(project)}</title><style>{STYLE}</style></head><body>
<main><header><div><p class="project">Factory <span>/</span> {text(project)}</p>
<h1>Stato dei lavori</h1></div>
<label class="refresh" hidden><input id="auto-refresh" type="checkbox" checked> Aggiornamento automatico</label></header>
<nav aria-label="Vai ai lavori per stato">{''.join(counts)}</nav>
<div class="board">{''.join(sections)}</div>
<footer>Le decisioni e le approvazioni di push e merge si danno nella chat del progetto.</footer>
</main><script>{REFRESH}</script></body></html>'''


STYLE = """
:root {color-scheme:light;--ink:#172a39;--muted:#485b69;--line:#cdd9dc;--accent:#0c635d}
* {box-sizing:border-box}
body {margin:0;color:var(--ink);background:#f4f7f6;font:1rem/1.5 Inter,system-ui,sans-serif}
main {max-width:83rem;margin:auto;padding:clamp(1rem,4vw,4rem)}
header {display:flex;align-items:end;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.project {font-weight:650;margin:0;color:var(--accent);overflow-wrap:anywhere}
.project span {color:#637c79;margin:0 .4em}
h1 {margin:.3rem 0 0;font-size:clamp(2.2rem,5vw,4rem);letter-spacing:-.05em;line-height:1.1}
.refresh {color:var(--muted);font-size:.9rem;cursor:pointer;padding:.5rem 0}
.refresh input {accent-color:var(--accent);width:1rem;height:1rem;vertical-align:text-bottom}
nav {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:2rem 0;gap:.6rem}
nav a {color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:.7rem;
       display:flex;flex-direction:column;text-decoration:none;padding:1rem 1.2rem}
nav a:first-child {background:#e9f3f0;border-color:#9cbfb7}
nav a:hover,summary:hover {text-decoration:underline;text-underline-offset:.2em}
nav span {color:var(--muted);font-weight:600;font-size:.9rem}
nav strong {font-size:2rem;font-variant-numeric:tabular-nums;line-height:1.3}
.board {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.6rem 1.15rem;align-items:start}
section {min-width:0;scroll-margin-top:1rem;border-top:2px solid var(--line)}
section:first-child {border-color:#39857a}
h2 {font-size:1.24rem;letter-spacing:-.025em;margin:.8rem 0}
.card {border:1px solid var(--line);background:white;border-radius:.65rem;padding:1rem;margin:.65rem 0;overflow-wrap:anywhere}
.card-head {display:flex;justify-content:space-between;gap:.6rem;align-items:baseline;flex-wrap:wrap}
.ticket {font:600 .78rem/1.4 ui-monospace,monospace;color:var(--muted)}
.badge {font-size:.78rem;font-weight:650;color:#264d70;background:#e7eff7;padding:.15rem .5rem;border-radius:.3rem}
.feedback .badge {color:#804612;background:#fff0ce}
.ok .badge,.ready .badge {color:#215b44;background:#dfefe4}
.ko .badge {color:#912838;background:#fbe4e7}
.queued .badge {color:#4c5965;background:#eaf0f2}
h3 {font-size:1.15rem;margin:.5rem 0 .1rem;letter-spacing:-.02em}
.note {white-space:pre-wrap;color:#374b58;font-size:.95rem;margin:.55rem 0 .1rem}
.pr {margin:.35rem 0;font-size:.9rem}.card a {color:var(--accent)}
.empty,footer {font-size:.9rem;color:var(--muted)}
.empty {padding:.6rem 0;margin:.65rem 0}
details {margin-top:.8rem;border-top:1px solid #e1e7e8}
summary {cursor:pointer;color:var(--accent);font-weight:600;font-size:.85rem;padding:.67rem 0 .1rem}
dl {display:grid;grid-template-columns: auto minmax(0,1fr);gap:.35rem 1rem;font-size:.85rem;margin:.65rem 0 0}
dt {color:var(--muted)} dd {margin:0;font-family:ui-monospace,monospace}
details h4 {font-size:.95rem;margin:1rem 0 .25rem}
details p,details li {font-size:.86rem;margin:.25rem 0;white-space:pre-wrap}
details ul,details ol {padding-left:1.25rem;margin:.45rem 0}
details time {display:block;color:var(--muted);font-size:.78rem}
.timeline li {padding:.4rem 0;border-top:1px solid #e1e7e8}
.votes dd {font-family:inherit}
footer {margin:2.4rem 0 .5rem;border-top:1px solid var(--line);padding-top:1rem}
:focus-visible {outline:3px solid #1b6391;outline-offset:3px}
@media(max-width:46rem){.board{grid-template-columns:1fr}nav{grid-template-columns:repeat(2,minmax(0,1fr))}
nav a{padding:.75rem}main{padding:1.1rem}dl{grid-template-columns:1fr;gap:.15rem}dd{margin-bottom:.3rem}}
[hidden]{display:none}
"""


REFRESH = """
const control = document.querySelector('.refresh');
const toggle = control.querySelector('input');
control.hidden = false;
const previousFocus = history.state?.factoryFocus;
if (previousFocus) document.getElementById(previousFocus)?.focus({preventScroll:true});
// Pause for reading, then restore the focused control even if its card changed section.
window.setInterval(() => {
  if (toggle.checked && !document.hidden && !document.querySelector('details[open]') &&
      !window.getSelection().toString()) {
    history.replaceState({factoryFocus:document.activeElement.id}, '');
    window.location.reload();
  }
}, 15000);
"""
