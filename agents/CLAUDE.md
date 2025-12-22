# MAKER Agents - Coordination Rules

This file is lazy-loaded when working with agent definitions.

## Agent Responsibilities

| Agent | Role | Model |
|-------|------|-------|
| maker-decomposition | Break tasks into atomic steps (m=1) | inherit |
| maker-decomposition-discriminator | Validate decomposition quality | inherit |
| maker-solver | Execute exactly ONE atomic step | inherit |
| maker-red-flag | Validate solver outputs (<750 tokens) | haiku |
| maker-solution-discriminator | Vote on critical step candidates | inherit |
| maker-reviewer | Final quality gate (zero issues) | inherit |
| maker-complexity-estimator | Assess task complexity | inherit |
| maker-checkpoint-manager | Create/restore file checkpoints | haiku |
| maker-cache-manager | Cache decomposition patterns | haiku |
| maker-parallel-coordinator | Plan parallel execution waves | haiku |

## Tool Restrictions

Each agent has specific tools available:

- **maker-decomposition**: Read, Grep, Glob (NO Write/Edit)
- **maker-solver**: Read, Edit, Write, Bash, Grep, Glob (FULL access)
- **maker-red-flag**: Read, Grep (validation only)
- **maker-reviewer**: Read, Grep, Glob, WebFetch, WebSearch, Bash, QA MCP tools
- **maker-checkpoint-manager**: Read, Write, Bash, Glob
- **maker-cache-manager**: Read, Grep, Glob, Write

## Output Format Requirements

### maker-solver Output
Must include:
- [TASK_ID], [STEP], [STATUS] (SUCCESS/BLOCKED)
- ACTION TAKEN, OUTPUT STATE
- VERIFICATION, NEXT STEP INPUT (if SUCCESS)

### maker-red-flag Output
- [VERDICT]: VALID or FLAGGED
- [VIOLATIONS]: List if FLAGGED

### maker-reviewer Output
- [VERDICT]: APPROVED or NEEDS_FIXES
- Per-check findings with Required Fix for each issue

## Red-Flag Rules

Flag solver output if:
- Response exceeds 750 tokens
- Missing required fields
- Malformed format
- Status neither SUCCESS nor BLOCKED

## Voting Rules (Critical Steps)

1. Run 3 solver instances in parallel
2. Collect all candidates
3. Discriminator selects best using first-to-ahead-by-k
4. Use winning candidate's OUTPUT STATE for next step
