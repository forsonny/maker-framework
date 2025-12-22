---
description: Check current MAKER pipeline execution status
allowed-tools: Read, Glob
---

# MAKER Status Command

Check the status of the current MAKER pipeline execution.

## Actions

1. Read checkpoint files from `.maker-checkpoints/metadata/`
2. Display current step and progress
3. Show any pending or failed steps
4. Report cache hit statistics from `cache/decomposition-patterns/index.json`

## Output Format

```
==========================================
         MAKER PIPELINE STATUS
==========================================

[CURRENT TASK]
Task ID: {task_id or "None active"}
Started: {timestamp}
Status: {IN_PROGRESS | PAUSED | COMPLETED | FAILED}

------------------------------------------
PROGRESS
------------------------------------------
Steps Completed: {N} of {Total}
Current Step: {step name or "N/A"}
Last Checkpoint: {checkpoint_id}

------------------------------------------
STEP HISTORY
------------------------------------------
[001] {step_name} - COMPLETED
[002] {step_name} - COMPLETED
[003] {step_name} - IN_PROGRESS
[004] {step_name} - PENDING
...

------------------------------------------
CACHE STATISTICS
------------------------------------------
Cached Patterns: {count}
Cache Hits: {count}
Cache Misses: {count}
Hit Rate: {percentage}%

==========================================
```

## If No Active Pipeline

If no pipeline is currently running:

```
==========================================
         MAKER PIPELINE STATUS
==========================================

No active MAKER pipeline.

Last completed task: {task_id or "None"}
Completed at: {timestamp or "N/A"}

Use /maker-framework:maker <task> to start a new pipeline.

==========================================
```
