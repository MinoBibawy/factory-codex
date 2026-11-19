# Factory for Codex

Describe a problem in your project chat and ask Factory to work on it. Factory uses the analysis already in the conversation, follows your project's `AGENTS.md` files, and runs the project's own tests. Its local dashboard shows active jobs, questions that need your input, results, pull requests, and artifacts.

Factory replies in your preferred language. If you have not set a preference, it uses the language of your request. It puts the result or required action first and uses short, active sentences. Its style draws on ASD-STE100 Simplified Technical English, with an approximate 80% target adapted to each language.

## How Factory works

```text
+----------------------------------+
| Project chat                     |
| Describe the issue or paste the  |
| analysis, then ask /factory.     |
+----------------------------------+
                 |
                 v
+----------------------------------+       +-------------------------+
| Intake agent                     |------>| Waiting for your input  |
| Check the evidence and define    |       | Answer in project chat. |
| what a successful fix looks like.|<------| Resume the same job.    |
+----------------------------------+       +-------------------------+
                 |
                 v
+----------------------------------+       +-------------------------+
| What did the user ask for?       |------>| Diagnose or propose     |
| Fix or implement: continue below.|       | Deliver analysis.md and |
+----------------------------------+       | stop before development.|
                 |                         +-------------------------+
                 v
+----------------------------------+       +-------------------------+
| Does the change need a design    |--yes->| Elephant Goldfish       |
| decision?                        |       | Draft and independently |
+----------------------------------+       | review the spec.        |
                 | no                      +-------------------------+
                 |                                      |
                 v                                      |
+----------------------------------+                    |
| Developer                        |<-------------------+
| Implement in the job's worktree. |<-------------------+
+----------------------------------+                    |
                 |                                      |
                 v                                      |
+----------------------------------+                    |
| Tests and independent review     |--- findings --------+
| Run project tests. Review code,  |                    |
| security, quality and affected   |                    |
| UI, UX or backend behavior.      |                    |
+----------------------------------+                    |
                 | pass                                 |
                 v                                      |
+----------------------------------+                    |
| For bug fixes: intake agent      |--- still fails -----+
| Retry the original failing case. |
+----------------------------------+
                 | verified
                 v
+----------------------------------+       +-------------------------+
| What did you ask Factory to do?  |------>| Local fix               |
+----------------------------------+       | Mark OK on dashboard.   |
                 |                         +-------------------------+
                 | publish a PR
                 v
+----------------+    +----------------+    +------------------------+
| Draft PR       |--->| You approve    |--->| Push the exact commit  |
| Show evidence  |    | the push.      |    | and check CI.          |
| and merge risk.|    +----------------+    +------------------------+
+----------------+                                      |
                                                        | CI passes
                                                        v
                                           +------------------------+
                                           | You approve the merge. |
                                           | Factory verifies it.   |
                                           +------------------------+
```

Open the dashboard at any point to see active jobs, requests for feedback, results, pull requests, and artifacts.

Jobs waiting for feedback keep their evidence while other independent jobs proceed. A design-only request ends with the reviewed proposal.

## Installation

You need Codex with plugin support and native agents, Git, and Python 3 with `fcntl`. The queue commands have been tested with Python 3.9.6 and 3.14.7. On Linux or WSL, verify the queue and Git worktrees before adoption. Native Windows would require different process locking.

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
| Analyze or diagnose | Factory Analysis checks the code, versioned documentation and available project decisions. It returns the diagnosis, evidence and limits in the dashboard. |
| Find a solution | Adds a recommended change, meaningful alternatives and a verification case. To implement the proposal later, ask Factory to fix the issue. The developer reuses the analysis. |
| Bug fix or regression | Uses Poteto for intake and diagnosis and Ponytail during implementation. Runs project tests and independent reviews. For a small change, focuses frontend and backend checks on the affected layers. |
| Change with open design questions | Uses the relevant Compound Engineering stages. When a change needs a decision about behavior across components, public contracts, or persistent data, Elephant Goldfish (EGM) reviewers check the specification before implementation. |
| Pull request draft | Writes a local summary with before-and-after evidence, merge risk, and reversibility. The draft is available from the dashboard. |
| Remote delivery | Shows the repository, source and target branches, and exact commit before asking for approval. GitHub CI requires an authenticated `gh` client with read access. Other providers need an equivalent source of check results. |

For example, use `/factory analyze` for a diagnosis, `/factory find a solution` for a proposal, or `/factory fix it` to authorize local implementation. The intake agent can consult your project’s Obsidian vault when configured and accessible. Independent specialists can check code, contracts and project decisions in parallel. For high-risk conclusions a reviewer challenges the evidence before handoff.

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
