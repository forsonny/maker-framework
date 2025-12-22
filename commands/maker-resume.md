---
description: Resume MAKER pipeline from last checkpoint
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
argument-hint: [checkpoint-id]
---

# MAKER Resume Command

Resume pipeline execution from the last checkpoint or specified checkpoint.

## Process

1. If $ARGUMENTS provided, load that specific checkpoint
2. Otherwise, find most recent checkpoint in `.maker-checkpoints/metadata/`
3. Validate checkpoint state is consistent with file system
4. Resume execution from that point
5. Continue with normal MAKER pipeline flow

## Checkpoint Discovery

```bash
# List available checkpoints
ls -la .maker-checkpoints/metadata/*.json
```

## Resume Flow

```
==========================================
         MAKER RESUME
==========================================

[CHECKPOINT FOUND]
Checkpoint ID: {id}
Created: {timestamp}
Step: {N} of {Total}
Task ID: {task_id}

------------------------------------------
VALIDATION
------------------------------------------
Files Match: {yes/no}
State Valid: {yes/no}

------------------------------------------
RESUMING
------------------------------------------
Resuming from step {N}: {step_name}

[MAKER] Executing step {N}/{Total}...
...
```

## If No Checkpoints Found

```
==========================================
         MAKER RESUME
==========================================

No checkpoints found.

Possible reasons:
- No MAKER pipeline has been run in this directory
- Checkpoints were cleaned up after completion
- Pipeline failed before first checkpoint

Use /maker-framework:maker <task> to start a new pipeline.

==========================================
```

## If Checkpoint Invalid

```
==========================================
         MAKER RESUME
==========================================

[CHECKPOINT INVALID]
Checkpoint ID: {id}
Error: {description of mismatch}

The file system state does not match the checkpoint.

Options:
1. Restore checkpoint: Use maker-checkpoint-manager RESTORE operation
2. Start fresh: Use /maker-framework:maker <task>

==========================================
```
