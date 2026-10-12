# MAKER in Codex

MAKER 1.2.0 adds a Codex profile alongside the existing Claude Code profile.
It runs inside your authorized chat. The skills coordinate work; the Python
state helper records plans, checkpoints and supplied evidence. Neither one is
a background task scheduler or a guarantee that arbitrary generated code works.

## Install

From the repository directory, with Python 3.10+ and a current Codex CLI:

```powershell
python -m pip install -r qa_server/requirements.txt
codex plugin marketplace add .
```

Open Codex's plugin directory (`/plugins` in the CLI), select the **MAKER Framework**
local marketplace, and install **MAKER Framework**. Open a new chat in the project
you want to change. Installation is global: the same skills and QA MCP server
are available in other projects, without a per-project install or fixed target
path. For a local plugin update, refresh/reinstall the local package
and start a new chat so the installed cache contains the revised files.

If `codex plugin` is unavailable, the executable on PATH is too old for these
instructions. Use the CLI bundled with the current desktop app or update your CLI.
Do not replace unrelated Codex settings to get an old executable to start.

The manifest selects `codex/skills/`. Claude's `commands/`, `agents/`, hooks and
orchestrator skill remain in their existing profile. They are not Codex agent
types or commands. In Codex, use these requests:

| Request | Skill |
|---|---|
| Use MAKER to implement this task: ... | `maker-framework:maker` |
| Show MAKER status | `maker-framework:maker-status` |
| Resume the MAKER task | `maker-framework:maker-resume` |
| List/inspect/clear the MAKER cache | `maker-framework:maker-cache` |

The run skill supports complexity assessment, plan validation, bounded solvers,
output validation, critical-step voting, final review, retry, checkpoints, cache
reuse and independent read-only analysis. Native delegation availability and
repository rules determine which roles can run independently. Shared-checkout
mutations are sequential. Missing delegation is disclosed as self-review.

## QA

The Codex manifest bundles the global `maker-qa` MCP server using `.codex.mcp.json`.
Its Python process starts from the installed plugin, but every filesystem tool
requires an explicit absolute `working_dir` for the project being tested. It
never assumes the plugin folder is your project. Each call resolves source files,
baselines and configuration within the selected project; two projects can use
the same installation. No model API key or extra AI service is needed.

Installing globally does not authorize changing unrelated projects. Codex must
select the workspace for the current user request. No project-specific Codex
configuration or broad `QA_ALLOWED_PATHS` setting is needed. Python must be on
Codex's PATH with the QA requirements installed. The direct launcher remains
available if the host has not loaded the MCP server yet.

In PowerShell, substitute the actual absolute paths below:

```powershell
python 'C:\path\to\maker-framework\scripts\qa.py' --workspace 'C:\path\to\your-project' --tool ping
python 'C:\path\to\maker-framework\scripts\qa.py' --workspace 'C:\path\to\your-project' --tool run_tests
```

For tool parameters, write a JSON file and pass `--arguments @<absolute-json-file>`.
For example, `{"framework":"unittest","pattern":"test_*.py"}`. This avoids
PowerShell JSON quoting issues. The seven tools are `ping`, `run_tests`,
`get_coverage`, `check_regressions`, `generate_tests`, `check_prd_alignment`, and
`aggregate_qa_report`. Tests and coverage execute your project and its configured
hooks. Install its test runner and coverage dependencies in the Python/Node
environment used by the launcher.

In a new Codex chat, check that `maker-qa` connects and call `ping`. For a filesystem
tool, supply `working_dir` with the absolute target-project path. Omitting that
field, or supplying a relative path in global mode, fails instead of selecting
an accidental project. Relative source paths, baseline paths and `qa-config.yaml`
are then resolved for the chosen project. Keep baseline updates, generated tests,
and project state in that project, never in the global plugin installation.

PRD alignment only compares keywords, and generated tests are unfinished
scaffolds. Zero collected tests, skipped scaffolds, or coverage percentages do not
prove a requested feature works. Use real assertions and requirement review.

When no supported test framework is available, `run_tests`, `get_coverage` and
`check_regressions` return `status: "unavailable"`,
`code: "NO_SUPPORTED_TEST_FRAMEWORK"`, `tests_executed: 0` and a clear message.
Test counts are zero with no failures; coverage is unknown (`percentage: null`,
`meets_threshold: false`); regression comparisons are neutral. MCP `isError: true`
and direct-launcher exit 1 signal the unavailable check, not a failed product
test. Report that limitation without counting a pass or repairing unrelated
application code. Choose an existing project verification command or an available
native/host browser tool; do not invent a browser tool or install an unrequested
browser framework. An online preview does not verify offline behavior.

Solver and validator evidence should identify the source of expected outcomes
for logic-heavy checks. Requirements, independent examples and observable inputs
can support expectations; fixtures copying implementation algorithms must be
labeled and cannot alone establish independent correctness. For interactive
criteria, report the normal starting state, user actions and outcome, such as
opening search, typing a query and dismissing it. Distinguish fixture/tool failures
from app defects, and inspect state after a timeout before replaying a mutating
action. Keep checks minimal and directly affected.

## State and recovery

Run records are under `<project>/.maker/runs/`, with `.maker/current.json` pointing
to the current run. Each run keeps its plan, step evidence, before snapshots and
after hashes. `init --plan <path>` also records the plan's absolute `plan_ref`.
Use an absolute `--plan` path; relative `--plan` paths load from the caller's
current directory, unlike context and evidence reference paths below.
Optional plan-level or per-step `context_refs` map names such as `brief` and
`acceptance` to existing or planned artifact paths. Relative references resolve
from `--workspace`; absolute and external paths are allowed. `finish` accepts
repeated `--evidence-ref name=path` arguments stored as step `evidence_refs`;
`complete` accepts the same arguments stored as run `review_refs`. Both still
require `--evidence` text describing actual checks and results. Use existing
relevant artifacts; these fields do not require boilerplate documents. Old plans,
runs and commands without the optional fields remain usable.

Resume and status follow explicit references before searching broadly, inspect
file availability and current relevant contents, and still check output drift.
References are locators, not verification proof or operational authority; missing
references must not become invented evidence. Snapshot creation leaves existing
user changes in place. Status reads records without changing them. An `IN_PROGRESS` record is not a live-worker
signal. A new run cannot overwrite an unfinished one.

Before resuming, compare current files with the saved outputs. An interrupted
action may already have taken effect. Restoration is restricted to the active
step's declared files and requires explicit confirmation at the CLI; inspect
and preserve unrelated edits before using it. Completed runs remain as history.
Legacy `.maker-checkpoints/` hook records are not silently imported.

Project cache patterns live under `.maker/cache/`. Bundled examples are read-only
seeds. Clearing a project cache moves it into `.maker/cache-archive/` and leaves
snapshots and bundled examples intact.

## Verify this repository

```powershell
python -m unittest discover -s tests -v
```

The suite uses temporary projects and exercises the reproduced Python, MCP, and
recovery defects. Python coverage and pytest checks skip explicitly when their
optional dependencies are absent. The audit also records separate real Jest and
Mocha runs; those packages are not production dependencies of MAKER.

Packaging follows the supported Codex compatibility manifest and local marketplace
formats in [OpenAI's plugin documentation](https://developers.openai.com/plugins/build/plugins).
Command and agent conversion follows the
[Claude plugin migration guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin).
