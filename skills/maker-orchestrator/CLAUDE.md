# MAKER Orchestrator - Detailed Instructions

This file is lazy-loaded when working with the orchestrator skill.

## Execution Flow

1. **Cache Lookup**: `maker-framework:maker-cache-manager` (model: haiku)
2. **Complexity Estimation**: `maker-framework:maker-complexity-estimator`
3. **Decomposition**: `maker-framework:maker-decomposition`
4. **Validation**: `maker-framework:maker-decomposition-discriminator`
5. **Cache Store**: `maker-framework:maker-cache-manager` (if cache miss)
6. **Parallel Planning**: `maker-framework:maker-parallel-coordinator` (model: haiku)
7. **Execution Loop**: For each step:
   - Checkpoint: `maker-framework:maker-checkpoint-manager` (model: haiku)
   - Execute: `maker-framework:maker-solver`
   - Validate: `maker-framework:maker-red-flag` (model: haiku)
   - Retry up to 3x if flagged
8. **Critical Steps**: Run 3 solvers in parallel, use `maker-framework:maker-solution-discriminator`
9. **Review**: `maker-framework:maker-reviewer`
10. **Fix Loop**: If issues found, fix via `maker-framework:maker-solver`, re-review until APPROVED
11. **Cleanup**: `maker-framework:maker-checkpoint-manager` CLEANUP

## State Management

Each step receives INPUT_STATE and produces OUTPUT_STATE:
- Step 1 INPUT_STATE = initial project state
- Step N INPUT_STATE = Step N-1 OUTPUT_STATE
- Pass state via NEXT STEP INPUT section of solver output

## Retry Logic with Resume

When red-flag validation fails:
1. Capture the `agent_id` from the original solver Task invocation
2. Retry using `resume: "{agent_id}"` parameter
3. Include flag reasons in retry prompt
4. Solver sees previous attempt + feedback for self-correction

## Parallel Execution

When `maker-parallel-coordinator` returns PARALLELISM > 0%:
- Execute steps by wave instead of sequentially
- Use `run_in_background: true` for parallel steps
- Collect results with `TaskOutput` tool
- Validate all results before proceeding to next wave

## Review Loop Limit

- Max 3 review cycles
- If still failing after 3 cycles, stop and ask user for guidance
- Never mark DONE until reviewer returns APPROVED with zero issues

## Prompt Templates

See @prompts.md for all prompt templates used in each phase.

## Workflow Diagram

See @workflow.md for visual execution flow.
