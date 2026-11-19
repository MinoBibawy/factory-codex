---
name: factory-analysis
description: Analyze a project issue, find an evidence-backed solution, or prepare a diagnosis for an authorized fix. Use for Factory intake when code, documentation, or project decisions can explain the observed behavior.
---

# Factory analysis

The intake agent owns the analysis. Start from the user's question, earlier findings, applicable AGENTS.md files and the exact outcome requested. Answer in the user's preferred language, using short sentences and consistent terms. Follow Factory's rules for chat, artifacts and approvals.

| Request | Deliverable |
| --- | --- |
| Analyze or diagnose | State the observed behavior, evidence, confidence and open questions. Stop after the diagnosis. |
| Find or propose a solution | Deliver the diagnosis, the recommended change, and the result of a small trial when feasible. Stop after the proposal. |
| Fix or implement | Give the same findings to the developer. For a bug, preserve the original input and expected result for replay by the intake agent. |

For diagnosis and proposals, keep project sources, tests, documentation and knowledge notes unchanged. Inspect the existing behavior using read-only checks or a disposable fixture. Write the report only to the job's local artifacts. The coordinator owns the queue.

## Investigation and review

1. **Hypothesis and test.** Record the input, observed result and expected result. Separate facts reported in the chat from facts you verified. Follow relevant callers in the code. For bugs and performance issues use Poteto's diagnostic steps. Choose the smallest safe check that distinguishes plausible causes. Record the command or observation and the revision. If the evidence cannot distinguish them, say which input, trace or test is missing.
2. **Compare the sources.** Check what the code does, what the applicable version of the contract requires, and why the project chose that behavior. For a small job, do this yourself. When these questions can be answered independently, delegate scoped reads to a code investigator, a documentation reviewer or a project-knowledge researcher. Give each one a question and ask for evidence with a location and scope. Share only the context each needs.
   - Search the project's configured Obsidian vault by component, symptom and domain terms. Start from relevant notes or local links. Record the note title, date if available, and whether the decision is current. Check Confluence when the project's rules call for it and access is available. Use only sources authorized for this project. If a source is inaccessible or yields no match, record that distinction. Keep private note contents, personal paths and internal links out of public PRs and shared artifacts.
   - When sources disagree, compare their dates, versions, owners and areas of applicability. A passing test establishes current behavior. An approved contract establishes expected behavior within its scope. A note can explain an exception. If the conflict changes a product decision and the sources cannot settle it, ask one concrete question and explain what depends on the answer.
3. **Compare solutions** for a proposal or an implementation handoff. Start with the smallest change that fixes the verified cause. Consider another option only if it materially changes correctness, compatibility, cost, risk or reversibility. Explain why you recommend one and what evidence would change that choice. Give a verification case with an observable expected result.
4. **Challenge the conclusion** when risk or conflicting evidence warrants it. An independent reviewer checks the assumptions and tries a counterexample on an authorized local fixture or inspects contrary evidence. Use the bundled EGM review for the design decisions covered by Factory. If the review changes the conclusion, revise it and recheck the affected case. End a loop when the question is answered or another round would repeat the same evidence. Mark unresolved limits or return the decision to the user.

## Test the proposed change

When the test is local, safe and small, copy the affected code and the minimum synthetic inputs into a disposable directory outside the project. First run the original failing case against the original behavior. Apply only the proposed change in the copy. Run the same case and one neighboring case that must keep working. Prefer a negative control that rejects a plausible wrong fix, such as an unknown key that must still return no match. Record the input, expected and observed result, command, and limits for both cases in the report. Do not copy private data or run an untrusted project's installer to make a fixture.

If the trial fails, revise the proposal using the new evidence. Stop if the next attempt would repeat the same evidence. Leave the status pending with the reason and next check when a dependency, environment, cost or authorization prevents a decisive trial. A fixture result stays a fixture result even if its source was copied from a commit. Use commit verification only for cases actually run on that clean, exact commit. It does not grant permission to implement, push or merge.

## Decisions and handoff

Return the requested outcome, cited evidence, open limits and, when requested, the recommendation and verification case. Use references a reader can locate, such as a source file and symbol, a contract section and version, or a shareable decision reference. Save the diagnosis or proposal as `analysis.md` under the job's artifacts for analysis-only and proposal jobs. For a small implementation job, a concise intake receipt can hold the findings. Use the report when several sources or reviewers are involved. Identify the local files that materially support the conclusion. Use stable, non-sensitive labels for external decisions. The coordinator records report and source fingerprints with the proposal. When a later job implements it, compare those sources against the child's actual worktree. Recheck changed inputs and record how they affect the recommendation. For external sources, explicitly confirm the current decision or leave the job waiting. If the change overturns the recommendation, return to analysis before development.

When the remaining uncertainty needs a product decision, give the coordinator one question, its choices and their observable consequences. The coordinator records it on that job. Reuse the recorded answer on resume. An answer applies to that question only; writing it to the vault or approving a remote operation requires its own authorization.
