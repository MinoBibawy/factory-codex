"""Prepare and consume local, one-use publication requests. Remote reads only."""

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit


def git(directory, *args):
    try:
        result = subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True,
                                timeout=30 if args[0] == "ls-remote" else None)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Il remoto Git non ha risposto in tempo. Rileggere lo stato.") from exc
    if result.returncode:
        raise ValueError(f"Git non ha completato {args[0]}. Verifica il repository e le credenziali configurate.")
    return result.stdout.strip()


def repo_name(url):
    if "://" in url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "ssh", "file"} or parsed.query or parsed.fragment:
            raise ValueError("Destinazione remota non riconosciuta.")
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        return (host + parsed.path).removesuffix(".git")
    scp = re.fullmatch(r"(?:[^@/]+@)?([\w.-]+):([^:]+)", url)
    if scp:
        return "/".join(scp.groups()).removesuffix(".git")
    if Path(url).is_absolute():
        return url.removesuffix(".git")
    raise ValueError("Usa una destinazione remota Git identificabile.")


def remote_refs(path, remote, target, branch):
    refs = {}
    for line in git(path, "ls-remote", "--heads", remote, f"refs/heads/{target}", f"refs/heads/{branch}").splitlines():
        sha, ref = line.split("\t")
        refs[ref] = sha
    return refs


def snapshot(job, action, remote, target, summary, pr=None):
    path, branch = job["worktree"], job["branch"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", remote):
        raise ValueError("Nome del remote non valido.")
    if git(path, "check-ref-format", "--branch", target) != target or branch == target:
        raise ValueError("Il ramo di consegna deve essere distinto dal ramo destinazione.")
    if git(path, "branch", "--show-current") != branch:
        raise ValueError("Il worktree non è sul ramo del lavoro.")
    if action == "merge" and not (pr and re.fullmatch(r"[1-9][0-9]*", pr)):
        raise ValueError("Per il merge serve il numero della PR/MR verificata.")
    if git(path, "config", "--type=bool", "--default", "false", "--get", f"remote.{remote}.mirror") == "true":
        raise ValueError("Un remote mirror pubblica più riferimenti di quelli approvati.")
    urls = git(path, "remote", "get-url", "--push", "--all", remote).splitlines()
    if len(urls) != 1:
        raise ValueError("Il push deve avere una sola destinazione.")
    repo = repo_name(urls[0])
    if repo_name(git(path, "remote", "get-url", remote)) != repo:
        raise ValueError("La destinazione letta e quella di push sono diverse.")
    refs = remote_refs(path, remote, target, branch)
    head = git(path, "rev-parse", "HEAD")
    upstream = refs.get(f"refs/heads/{target}")
    published = refs.get(f"refs/heads/{branch}")
    if not upstream:
        raise ValueError("Il ramo di destinazione manca sul remote.")
    if git(path, "merge-base", job["base"], upstream) != job["base"]:
        raise ValueError("La destinazione non contiene ancora la base verificata del lavoro.")
    if action == "merge" and published != head:
        raise ValueError("Il commit della PR deve coincidere con il commit verificato e pubblicato.")
    if action == "merge":
        git(path, "merge-base", "--is-ancestor", upstream, head)
    if action == "push" and published:
        git(path, "merge-base", "--is-ancestor", published, head)
    if not summary.strip() or len(summary) > 400 or len(summary.splitlines()) != 1:
        raise ValueError("Descrivi la modifica in una riga, entro 400 caratteri.")
    stat = git(path, "diff", "--shortstat", f"{upstream}...{head}")
    if not stat:
        raise ValueError("Nessuna modifica da proporre rispetto alla destinazione.")
    return dict(action=action, repo=repo, branch=branch, target=target, sha=head, remote=remote,
                target_sha=upstream, published_sha=published, summary=summary, stat=stat, pr=pr)


def bullets(card):
    destination = card["target"] if card["action"] == "merge" else card["branch"]
    pr = f" · PR/MR #{card['pr']}" if card["pr"] else ""
    return "\n".join([
        f"- {card['action'].upper()}{pr} · {card['summary']} ({card['stat']})",
        f"- Repository: {card['repo']} · remote: {card['remote']}",
        f"- Branch: {card['branch']} → {card['remote']}/{destination} · base PR: {card['target']} @ {card['target_sha'][:12]}",
        f"- Commit: {card['sha']}",
    ])


def valid_pr_url(repo, number, url):
    if not isinstance(url, str) or not isinstance(repo, str) or not re.fullmatch(r"[1-9][0-9]*", str(number)):
        return False
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
    except ValueError:
        return False
    if (parsed.scheme != "https" or not host or parsed.username is not None or parsed.query or parsed.fragment
            or any(c.isspace() or ord(c) < 32 for c in url) or "\\" in unquote(url)
            or any(part in ("", ".", "..") for part in unquote(parsed.path).split("/")[1:])):
        return False
    return any(url == f"https://{repo}/{route}/{number}" for route in
               ("pull", "-/merge_requests", "pull-requests", "pulls", "pullrequest"))


def verify_pr(card, data, link_only=False):
    try:
        head, base = data["head"], data["base"]
        actual = (str(data["number"]), data["state"], repo_name(head["repo"]["clone_url"]),
                  head["ref"], head["sha"], repo_name(base["repo"]["clone_url"]), base["ref"], base["sha"])
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("Dati PR incompleti: rileggi la richiesta dal provider.") from error
    number, state = actual[:2]
    if not re.fullmatch(r"[1-9][0-9]*", number) or state not in ("open", "closed", "merged"):
        raise ValueError("Numero o stato PR non valido.")
    expected = (card.get("pr") or number, state if link_only else "open", card["repo"], card["branch"],
                card["sha"], card["repo"], card["target"], base["sha"] if link_only else card["target_sha"])
    if actual != expected:
        raise ValueError("PR, stato, repository, rami o commit discordanti. Rileggi i riferimenti.")
    url = data.get("html_url") or data.get("web_url")
    if valid_pr_url(card["repo"], number, url):
        return {"repo": card["repo"], "number": number, "url": url}
    if link_only:
        raise ValueError("Serve l’URL HTTPS della PR restituito dal provider per il repository e il numero verificati.")


def request(job, card):
    if (card['action'] == 'push' and job.get('ci', {}).get('status') == 'fail'
            and job['ci']['sha'] == card['sha']):
        raise ValueError('La CI è fallita su questo commit. Verificare una correzione su un nuovo SHA.')
    if job["stage"] != "ready":
        raise ValueError("Serve un lavoro pronto con test e revisioni completati.")
    receipt = uuid.uuid4().hex
    job.update(stage="feedback", feedback_from="ready", note=bullets(card),
               delivery={**card, "status": "waiting", "receipt": receipt,
                         "requested_at": datetime.now(timezone.utc).isoformat()})
    return receipt


def consume(job, card, action, receipt):
    pending = job.get("delivery", {})
    if (job["stage"] != "feedback" or pending.get("status") != "waiting"
            or pending.get("action") != action or pending.get("receipt") != receipt):
        raise ValueError("Manca una richiesta di approvazione corrispondente e ancora aperta.")
    if any(pending.get(k) != value for k, value in card.items()):
        raise ValueError("Riferimenti o contenuto cambiati. Annulla e presenta una nuova anteprima.")
    pending["status"] = "confirmed"
    if action == "push":
        from ci import receipt as ci_receipt
        job['ci'] = ci_receipt(pending)
    job.update(stage="ready", feedback_from=None, note=f"{action.capitalize()} autorizzato per {card['sha'][:12]}.")


def main():
    import ci
    import factory
    import quality

    commands = argparse.ArgumentParser()
    subs = commands.add_subparsers(dest="cmd", required=True)
    prepare = subs.add_parser("prepare")
    prepare.add_argument("id")
    prepare.add_argument("action", choices=("push", "merge"))
    prepare.add_argument("remote")
    prepare.add_argument("target")
    prepare.add_argument("summary")
    prepare.add_argument("--pr")
    prepare.add_argument("--pr-json", type=Path)
    confirm = subs.add_parser("confirm")
    confirm.add_argument("id")
    confirm.add_argument("action", choices=("push", "merge"))
    confirm.add_argument("receipt")
    confirm.add_argument("--pr-json", type=Path)
    cancel = subs.add_parser("cancel")
    cancel.add_argument("id")
    record = subs.add_parser("record-pr")
    record.add_argument("id")
    record.add_argument("--pr-json", type=Path, required=True)
    observe = subs.add_parser("ci")
    observe.add_argument("id")
    for command in (observe, prepare, confirm):
        command.add_argument("--ci-json", type=Path, help="Snapshot appena letto dal connettore del provider")
    args = commands.parse_args()
    job = factory.get(args.id)
    if args.cmd == "ci":
        print(json.dumps(ci.refresh(job, args.ci_json)['ci'], ensure_ascii=False))
        return
    if args.cmd == "record-pr":
        data = json.loads(args.pr_json.read_text(encoding="utf-8"))
        def record_link(current):
            card = current.get("delivery", {})
            if not (card.get("action") == "merge" or
                    card.get("action") == "push" and card.get("status") == "confirmed"):
                raise ValueError("Serve una consegna con push confermato o una PR verificata per il merge.")
            current["pull_request"] = verify_pr(card, data, link_only=True)
        saved = factory.mutate(args.id, record_link)
        print(saved["pull_request"]["url"])
        return
    if args.cmd == "cancel":
        def withdraw(current):
            pending = current.get("delivery", {})
            if current["stage"] != "feedback" or pending.get("status") != "waiting" or pending != job.get("delivery"):
                raise ValueError("Nessuna richiesta corrispondente da ritirare.")
            pending["status"] = "cancelled"
            current.update(stage="ready", feedback_from=None, note="Richiesta ritirata. Nessuna pubblicazione autorizzata.")
        factory.mutate(args.id, withdraw)
        return
    quality.verify_job(job)
    if args.cmd == "prepare":
        card = snapshot(job, args.action, args.remote, args.target, args.summary, args.pr)
    else:
        pending = job.get("delivery", {})
        if pending.get("status") != "waiting" or pending.get("action") != args.action:
            raise ValueError("Nessuna richiesta aperta per questa operazione.")
        card = snapshot(job, args.action, pending["remote"], pending["target"], pending["summary"], pending["pr"])
    link = None
    if args.action == "merge":
        if not args.pr_json:
            raise ValueError("Occorre una lettura aggiornata della PR dal provider (--pr-json FILE).")
        link = verify_pr(card, json.loads(args.pr_json.read_text(encoding="utf-8")))
        job = ci.refresh(job, args.ci_json)
        ci.require_pass(job, card)
        refs = remote_refs(job['worktree'], card['remote'], card['target'], card['branch'])
        if (refs.get('refs/heads/' + card['target']) != card['target_sha'] or
                refs.get('refs/heads/' + card['branch']) != card['sha']):
            raise ValueError('Un ramo remoto è cambiato durante la verifica CI. Ripresentare il merge.')
    result = []

    def save(current):
        quality.verify_job(current)
        if args.action == 'merge':
            ci.require_pass(current, card)
        if card["sha"] != git(current["worktree"], "rev-parse", "HEAD"):
            raise ValueError("Il commit è cambiato.")
        if args.cmd == "prepare":
            result.append(request(current, card))
        else:
            consume(current, card, args.action, args.receipt)
        if link:
            current["pull_request"] = link

    factory.mutate(args.id, save)
    print(bullets(card))
    if result:
        print(f"\nRicevuta locale: {result[0]}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        sys.exit(str(error))
