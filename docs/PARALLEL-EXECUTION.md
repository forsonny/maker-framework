# Parallel Execution in MAKER

This document explains how the MAKER framework executes independent steps in parallel for improved pipeline throughput.

## Overview

MAKER's distributed execution support allows independent step branches to run concurrently, reducing total pipeline execution time. Instead of executing all steps sequentially, steps that have no dependencies on each other can run in parallel "waves."

## How It Works

### Step Marking

During decomposition, each step is marked with a `Parallel` flag:

```
[001] Create config file
  |- Parallel: no    <- Must run first, others depend on it

[002] Create user model
  |- Depends: [001]
  |- Parallel: yes   <- Can run alongside [003]

[003] Create product model
  |- Depends: [001]
  |- Parallel: yes   <- Can run alongside [002]
```

### Parallel Coordinator

After decomposition validation, the `maker-parallel-coordinator` agent analyzes the step dependencies and organizes them into execution waves:

```
Wave 1 (Sequential): [001]
Wave 2 (Parallel):   [002], [003]  <- Run concurrently
Wave 3 (Sequential): [004]
```

### Wave Execution

The orchestrator executes each wave:

1. **Sequential waves** (1 step): Execute normally
2. **Parallel waves** (2+ steps): Launch all steps using `run_in_background: true`, then collect results with `TaskOutput`

## Performance Benefits

| Scenario | Sequential Time | Parallel Time | Speedup |
|----------|-----------------|---------------|---------|
| 3 independent file creations | 3x | 1x | 3x |
| 2 parallel + 1 sequential | 3x | 2x | 1.5x |
| Fully dependent chain | Nx | Nx | 1x |

The speedup depends on how many steps can run in parallel. The `PARALLELISM` percentage reported by the coordinator indicates what fraction of steps benefit from parallelism.

## When Parallelism Applies

Steps can run in parallel when:

1. **No mutual dependencies**: Neither step depends on the other
2. **No file conflicts**: Steps don't modify the same files
3. **Both marked `Parallel: yes`**: Decomposer identified them as safe

Steps that should NOT run in parallel:

- Steps that modify the same file
- Steps where one depends on the other's output
- Steps marked `Parallel: no` by the decomposer
- Critical steps requiring voting (these use parallel voting instead)

## Progress Output

When parallel execution is active, progress shows wave-based output:

```
[MAKER] Executing wave 2 (parallel: 3 steps)...
  [2a/8] Creating user model...
  [2b/8] Creating product model...
  [2c/8] Creating order model...
[MAKER] Wave 2 complete (all 3 steps succeeded). Executing wave 3...
```

## Limitations

1. **Checkpoint handling**: Each step in a parallel wave creates its own checkpoint. Rollback restores all files from that wave.

2. **Error propagation**: If one step in a parallel wave fails:
   - Other steps in the wave continue to completion
   - Failed step retries independently
   - Wave completes only when all steps pass or exhaust retries

3. **State merging**: When parallel steps complete, their OUTPUT STATEs are available to subsequent steps based on explicit dependencies.

## Configuration

Parallel execution is automatic when the decomposition contains parallelizable steps. To disable:

```
[GRANULARITY]
merge_trivial: true   # Merges steps, reducing parallel opportunities
```

Or mark steps as `Parallel: no` in the decomposition.

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main orchestration documentation (Step 2b, Step 3-parallel)
- [maker-parallel-coordinator.md](../subagents/maker-parallel-coordinator.md) - Coordinator subagent specification
- [maker-progress-phases.md](maker-progress-phases.md) - Progress output phases

## Implementation Details

### Parallel Coordinator Invocation

```
Task(
  subagent_type: "maker-parallel-coordinator",
  description: "maker-parallel-coordinator: Planning parallel execution waves",
  model: "haiku",
  prompt: {PARALLEL EXECUTION PLANNING request}
)
```

### Parallel Wave Execution

```
// Launch all steps in parallel
for step in wave.steps:
  task_ids.append(
    Task(
      subagent_type: "maker-solver",
      run_in_background: true,
      ...
    )
  )

// Collect all results
for task_id in task_ids:
  results.append(TaskOutput(task_id, block: true))
```

### Success Metric

Linear scaling with available compute for parallelizable tasks. A decomposition with 50% parallelism (half the steps can run in parallel) should complete in roughly 75% of the sequential time.
