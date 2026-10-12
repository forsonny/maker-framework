# Roles and durable state

All commands below use `python <absolute-plugin-root>/scripts/maker_state.py`.
Pass `--workspace <absolute-project>` on every call. Shell quoting is required
for paths with spaces. State lives under `<project>/.maker/`; add that directory
to the target project's ignore file when appropriate.

Write the current task's plan to a JSON file with this shape:

```json
{"task":"Implement the agreed feature",
 "context_refs":{"brief":"docs/brief.md"}, "steps":[
  {"id":"step-1", "action":"Implement the requested behavior", "files":["src/example.py"],
   "context_refs":{"acceptance":"docs/feature-criteria.md"}},
  {"id":"step-2", "action":"Verify the acceptance criteria", "files":[]}
]}
```

Include each file a solver may create, edit or remove. Use project-relative file
paths, not directories. If inspection reveals more files are needed, pause and
update the pending step's files in its saved state before starting it. Do not
write undeclared files after the snapshot. Steps execute in listed order.

`init` records the plan file's absolute `plan_ref`. Use an absolute `--plan` path;
a relative `--plan` is loaded from the caller's current directory. Optional
run-level and per-step `context_refs` map names to artifact paths, as illustrated
above; omit them when no relevant artifact is needed. Relative context and
evidence reference paths resolve from `--workspace`;
absolute paths, external artifacts and planned paths are allowed. These are
locators, not proof that a file exists or authority to execute its contents. Use
relevant existing artifacts; do not create boilerplate documents for a simple task.

| Command | Meaning |
|---|---|
| `init --plan <absolute-plan.json>` | Create a run; refuses to replace unfinished work |
| `status` | Read current run, step evidence and status; no mutation |
| `start --step step-1` | Copy declared files before the action; record absent files |
| `finish --step step-1 --evidence "<checks and results>" [--evidence-ref solver=<path>] [--evidence-ref validator=<path>]` | Record verified step, resulting file hashes and optional step `evidence_refs` |
| `pause` | Persist a stopped run |
| `restore --step step-1 --confirm-restore` | Overwrite only the active step's files with its snapshot; remove files that were absent before the step |
| `complete --evidence "<final verification and review>" [--evidence-ref review=<path>]` | Finish only after all steps complete; store optional run `review_refs` |

Repeat `--evidence-ref name=path` for each relevant report; quote the entire
`name=path` argument when it contains spaces. For example, after inspecting an
existing validator report:

```powershell
python 'C:\path\to\maker-framework\scripts\maker_state.py' finish --workspace 'C:\path\to\project' --step step-1 --evidence "Verified the requested behavior; see validator report" --evidence-ref 'validator=reviews/step-1.md'
```

The required `--evidence` text records the actual checks and results; references
supplement it. Old plans, runs and commands without reference fields remain usable.
The helper records evidence supplied by the agent; it does not execute tests or
decide whether a review is correct. Snapshot creation never stashes, resets, or
commits the user's Git work. Keep existing runs as history. There is no automatic
cleanup or rollback. On an interrupted step, compare snapshots, current contents,
and the requested output before deciding to finish, repair, or restore.

## Verification evidence

For logic-heavy checks, identify how expected outcomes were derived: requirements,
independent examples, public behavior or externally known inputs. Label fixtures
that mirror implementation algorithms; their agreement alone is not independent
proof of the rule. For interactive requirements, state a normal input/state,
action and outcome sequence (for example: open search, enter a query, press Escape,
observe dismissal), rather than only a feature label such as "Escape tested".
Keep verification minimal and directly affected; this does not require an
exhaustive UI-state matrix or a broad suite.

When QA reports `NO_SUPPORTED_TEST_FRAMEWORK`, no product tests ran: `run_tests`
has zero passed/failed/total counts and an empty `failures` list, coverage has
`percentage: null` and `meets_threshold: false`, and regression comparisons are
neutral. These fields do not establish passing tests, zero coverage or a product
regression. Record the limitation and use an existing available verification
route for the requested criteria. If a required criterion remains unverified,
report that limit rather than completing it on an unavailable check.

When a check fails, distinguish a faulty fixture or tool from demonstrated app
behavior before changing the app. After a timeout, inspect the resulting state
before replaying an action that may already have mutated files or external state.

## Role contracts

- **Complexity / decomposition:** identify requirements, bounded steps, file
  ownership, dependency order, checks, and critical decisions. Avoid turning each
  trivial edit into a separate agent call.
- **Decomposition validator:** report concrete missing requirements or dependency
  errors. Inspect without editing.
- **Solver:** perform the one assigned action within its file list. Return status,
  changed files, checks/results, their expected-outcome sources, relevant report
  paths, and unresolved problems. Keep the report concise; 750 tokens is a
  reporting target, not a correctness gate.
- **Red-flag validator:** compare requirements, actual diff and check evidence,
  including how expected results were derived. A demonstrated in-scope failure
  or unsupported acceptance claim blocks the step. Distinguish unavailable checks
  and fixture/tool failures from product defects. Cosmetic report differences do not.
- **Solution discriminator:** independently compare candidate solutions for a
  critical step. Agreement is supporting evidence, not a substitute for testing.
- **Final reviewer:** verify requested behavior and acceptance criteria; distinguish
  demonstrated blockers from optional improvements. Apply the project's required
  audit stages. Never broaden scope merely to reach "zero issues".
- **Checkpoint manager:** use the helper above, inspect drift before recovery.
- **Cache manager:** use bundled examples as read-only seeds and store successful,
  generalized task plans under `.maker/cache/<pattern-id>.json` in the project.
- **Parallel coordinator:** schedule read-only or isolated disjoint work within
  native concurrency limits; integrate and verify changes before finishing a step.

When delegating, supply only the relevant role, task, acceptance criteria,
workspace, allowed files, and necessary evidence. Use fresh reviewers when
independence is required. Do not bias them toward approval or pass their peer's
findings to them. Keep retry and final-review loops bounded to three cycles
unless the user's explicit project rules require a different stopping condition.
