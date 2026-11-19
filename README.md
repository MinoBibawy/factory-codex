# Factory for Codex

Describe a problem in your project chat and ask Factory to work on it. Factory uses the analysis already in the conversation, follows your project's `AGENTS.md` files, and runs the project's own tests. Its local dashboard shows active jobs, questions that need your input, results, pull requests, and artifacts.

## How Factory works

```text
Project chat: describe the problem, then ask /factory to fix it
    |
    v
Queue the job and open the local dashboard
    |
    v
Intake agent: check the evidence and agree on a testable outcome
    |
    +-- Missing information? --> Ask in chat, then resume the job
    |
    +-- Design decision? ------> Draft a spec and review it with EGM
    |
    v
Implement in the job's worktree
    |
    v
Run project tests and independent code, security, and quality reviews
    |
    +-- Finding or failed check? --> Fix it and repeat the checks
    |
    v
For bug fixes, the intake agent retries the original failing case
    |
    +-- Still fails? --> Return to development
    |
    +-- Local work complete? --> Record the result in the dashboard
    |
    v
Remote delivery requested
    |
    +-- Prepare a local PR draft if requested
    v
Approve push in chat --> Push the approved commit --> Check CI
    |
    +-- CI fails? --> Fix, retest, and request approval for a new push
    |
    v
If a merge was requested: approve it separately, then verify the merge
```

Jobs waiting for feedback keep their evidence while other independent jobs proceed. A design-only request ends with the reviewed proposal.

## Installation

You need Codex with plugin support and native agents, Git, and Python 3 with `fcntl`. Factory has been tested on macOS arm64. The queue commands have been tested with Python 3.9.6 and 3.14.7. On Linux or WSL, verify the queue and Git worktrees before adoption. Native Windows would require different process locking.

Clone this repository or extract the release package to a folder you intend to keep. From the folder containing this README, run:

```sh
codex plugin marketplace add "$PWD" && codex plugin add factory@factory-tools
```

Open a project chat and choose **Factory** from the skill picker. Use the qualified name `$factory:factory` if you also have an earlier standalone installation. The plugin installs its specialists together. Your Codex installation provides the chat credentials and native agents, and your project provides its development tools.

## Your first job

In the same chat as your analysis, write:

```text
Saving a label leaves trailing spaces. The previous message has the failing example. /factory fix it
```

Factory interprets `/factory` in the message. If your client does not select the skill automatically, choose `$factory:factory` and send the message. Use `/factory dashboard` to view the queue. To resume interrupted work, ask Factory to resume the job in the project chat. If native agents are unavailable, you can still view its status and see which assignment is waiting.

| Request | What Factory does |
| --- | --- |
| Bug fix or regression | Uses Poteto for intake and diagnosis and Ponytail during implementation. Runs project tests and independent reviews. For a small change, focuses frontend and backend checks on the affected layers. |
| Change with open design questions | Uses the relevant Compound Engineering stages. When a change needs a decision about behavior across components, public contracts, or persistent data, Elephant Goldfish (EGM) reviewers check the specification before implementation. |
| Pull request draft | Writes a local summary with before-and-after evidence, merge risk, and reversibility. The draft is available from the dashboard. |
| Remote delivery | Shows the repository, source and target branches, and exact commit before asking for approval. GitHub CI requires an authenticated `gh` client with read access. Other providers need an equivalent source of check results. |

## Data and permissions

Run Factory in a trusted project. Test commands run in the job's worktree with the permissions of the current process. For third-party tests, inspect scripts and configuration first and use an isolated environment with only the credentials they need. Factory records command arguments, so keep tokens and secrets off the command line. Push and merge previews read from the configured Git remote.

Factory stores the queue, evidence, and dashboard under `factory/` in the common Git directory. Outside Git, it uses `.factory/`. Artifacts can contain project information. Select individual files when sharing results.

## Uninstall

```sh
codex plugin remove factory@factory-tools
```

The project's queue and evidence remain available after you remove the plugin.

## Credits and licenses

Factory's original material is available under the [MIT license](plugins/factory/LICENSE). The [third-party notices](plugins/factory/THIRD_PARTY.md) document the bundled components, their licenses, and adaptations for Codex. Factory for Codex draws inspiration from [ZazenCodes' Factory v2 at the referenced revision](https://github.com/zazencodes/zazencodes-season-3/tree/c467603d6d62392cfaae0c07d2f701e99e111443/src/software-factory-claude-code-v2).
