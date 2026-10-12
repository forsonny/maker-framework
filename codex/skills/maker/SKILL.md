---
name: maker
description: Execute a MAKER development pipeline with task decomposition, bounded solver delegation, independent validation, and durable checkpoints. Use for requests to use MAKER or a systematically verified multi-step implementation; ordinary small edits do not need a pipeline.
---

# MAKER for Codex

Use the user's requested scope and repository instructions as the completion contract.
MAKER is an agent workflow, not a background service or a guarantee of zero errors.

Resolve the plugin root from this file: `../../..`. Resolve the target workspace
from the user's project, independently of the plugin installation directory.
Use Python 3.10+ and the scripts under the plugin root. Quote absolute paths.

1. Inspect the project and define the acceptance criteria. Assess complexity; use
   only enough steps to make ownership and verification clear.
2. Check `.maker/cache/` and the bundled `cache/decomposition-patterns/` for a
   relevant plan. Treat matches as suggestions and revalidate them against the
   current project. Keep mutable patterns in the workspace, never the plugin cache.
3. Decompose into bounded actions with explicit files and checks. Use an
   independent read-only agent to check completeness and ordering if native
   delegation is available. Read [workflow.md](workflow.md) for role contracts,
   voting, and the state commands.
4. Save a plan and initialize durable state. Link relevant existing brief,
   acceptance and review artifacts as described in [workflow.md](workflow.md).
   Before each step, run `start` to snapshot its declared files. Inspect the
   existing diff first. The orchestrator
   may write plans/state and run helpers; delegate implementation to a solver
   using the native subagent tools actually exposed by the host. Do not invoke
   Claude's Task tool, named Claude subagent types, or hard-code model names.
   Follow user/repository model-selection rules. Subagents must not delegate.
5. Inspect the solver's actual diff and verification output, including the source
   of expected outcomes and normal user sequences for interactive requirements.
   Use a fresh read-only validator for the requested behavior. A short, well-formed
   response alone is not proof. Record successful verification with `finish` and
   references to relevant reports. Retry only a concrete in-scope failure, up to
   three attempts; after that pause with the evidence.
6. For a critical or disputed step, obtain independent candidate reasoning in
   read-only agents before implementation. Compare against requirements and
   checks. Use first-to-ahead-by-2 with at most five votes; no consensus means
   unresolved, not approval. Do not rerun side-effecting actions to obtain votes.
7. Run the minimum final checks and independent review required by the project.
   Fix demonstrated blocking defects only. Record `complete` with the review
   evidence after every step passes. Store a reusable local pattern if useful.

Native delegation is requested by this workflow, subject to host instructions.
If unavailable or prohibited, explain the limitation and use sequential roles;
label review as self-review and never claim independent validation occurred.
Parallelize read-only analysis or isolated work with disjoint files. The shared
workspace state helper supports one mutating step at a time; do not concurrently
call it or run multiple writers in the same checkout.

QA: the globally installed plugin exposes `maker-qa`. Use its connected tools
when available. Otherwise run the bundled
`scripts/qa.py --workspace <absolute-project> --tool <name> --arguments @<json-file>`.
Always pass the actual target project as `working_dir` to connected QA tools.
The global server requires that absolute path on every filesystem tool call and
has no default target project. Global installation does not authorize work on
unrelated projects; use the workspace selected for the user's current task.
Tool names: `ping`, `run_tests`, `get_coverage`, `check_regressions`,
`generate_tests`, `check_prd_alignment`, `aggregate_qa_report`.
Test execution and coverage run project code and configured hooks; use only the
authorized project. Generated tests are scaffolds needing real assertions.
PRD alignment is keyword matching. Neither heuristic scores, skipped tests, nor
zero collected tests establish acceptance. With no supported test framework,
`run_tests`, `get_coverage` and `check_regressions` return `status: "unavailable"`,
`code: "NO_SUPPORTED_TEST_FRAMEWORK"` and `tests_executed: 0`. MCP `isError: true`
or CLI exit 1 represents an unavailable check, not a failing product test. Do
not count it as a pass or repair unrelated application code. Use existing project
verification commands or native/host browser tools when actually available; do
not invent a browser tool or add an unrequested browser framework. Check an
offline requirement through the offline artifact; an online preview cannot
establish it. See [workflow.md](workflow.md) for interpreting verification evidence.

Resume uses the stored plan and current files; see the `maker-resume` skill.
Never apply legacy Git-stash checkpoint instructions or Claude hook events to
Codex state. Rollback requires inspecting affected files and authorization for
the overwrite; preserve unrelated changes. Report progress without claiming a
persisted `IN_PROGRESS` record proves that an agent is currently running.
