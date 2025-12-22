# Rollback and Recovery

This document explains the checkpoint and rollback system in the MAKER framework, which enables graceful recovery from mid-pipeline failures.

---

## Overview

The MAKER framework creates automatic checkpoints before each step executes. If a step fails after exhausting all retries, the system can roll back to the last known good state, allowing the pipeline to:

1. **Recover gracefully** from partial file modifications
2. **Retry with different approaches** without corrupted state
3. **Preserve user work** when the pipeline cannot continue

---

## How It Works

### Checkpoint Creation (Automatic)

Before each step in the execution loop, the orchestrator:

1. Identifies which files the step will modify (from the decomposition's Output field)
2. Invokes `maker-checkpoint-manager` with operation `CREATE`
3. Captures a snapshot of those files
4. Stores checkpoint metadata for later restoration

```
Step N about to execute
    |
    v
[CREATE checkpoint ckpt-{task}-step-{N}]
    |
    v
Files captured: src/utils/helper.ts, src/types.ts
    |
    v
Step N executes normally
```

### Rollback Triggers

The system automatically triggers rollback when:

| Trigger | Condition | Rollback To |
|---------|-----------|-------------|
| **Retry Exhausted** | Solver fails 3 times on a step | Checkpoint before failed step |
| **Critical Step All-Fail** | All 3 voting candidates fail | Checkpoint before critical step |
| **Review Loop Exceeded** | Review cycle repeats 3+ times | Checkpoint before first fix attempt |
| **Blocked Step** | Solver returns BLOCKED with unrecoverable error | Checkpoint before blocked step |

### Restore Process

When rollback is triggered:

1. Orchestrator invokes `maker-checkpoint-manager` with operation `RESTORE`
2. Checkpoint manager restores files to their pre-step state:
   - Files that existed: Restored to checkpoint version
   - Files created by failed step: Deleted
3. Pipeline reports the rollback to the user
4. Orchestrator may request decomposition revision or user guidance

```
Step 4 fails after 3 retries
    |
    v
[RESTORE checkpoint ckpt-task123-step-4]
    |
    v
src/utils/helper.ts: restored
src/newfile.ts: deleted (didn't exist before)
    |
    v
Report to user: "Step 4 failed. Rolled back to pre-step state."
```

### Cleanup (After Success)

When the pipeline completes successfully:

1. Orchestrator invokes `maker-checkpoint-manager` with operation `CLEANUP`
2. All checkpoints except the last one are removed
3. Storage is reclaimed

---

## Checkpoint Strategies

### Git-Based (Preferred)

When working in a git repository, checkpoints use git stash:

- **Faster**: Leverages git's efficient file tracking
- **Smaller**: No file duplication
- **Integrated**: Works with existing git workflows

```bash
# Under the hood
git stash push -m "maker-checkpoint: ckpt-task123-step-4" -- src/utils/helper.ts
```

### File-Copy (Fallback)

When not in a git repository:

- **Universal**: Works in any directory
- **Isolated**: Copies stored in `.maker-checkpoints/files/`
- **Larger**: Full file copies require more storage

```
.maker-checkpoints/
  metadata/
    ckpt-task123-step-4.json
  files/
    ckpt-task123-step-4/
      src/utils/helper.ts
```

---

## Configuration Options

### Disable Checkpoints

To run without checkpoints (not recommended for complex pipelines):

```
[MAKER_OPTIONS]
checkpoints: disabled
```

Or verbally: "Skip checkpoints for this task"

### Manual Checkpoint

Force a checkpoint at any point:

```
/maker checkpoint create
```

### Manual Rollback

Force rollback to a specific checkpoint:

```
/maker rollback ckpt-task123-step-4
```

### View Checkpoints

List available checkpoints:

```
/maker checkpoints list
```

---

## User Commands

| Command | Description |
|---------|-------------|
| `skip checkpoints` | Disable automatic checkpoints for current task |
| `force rollback` | Manually trigger rollback to last checkpoint |
| `show checkpoints` | Display available checkpoints and their states |
| `cleanup checkpoints` | Manually remove all checkpoints |

---

## When Rollback Occurs

The orchestrator will inform you when rollback happens:

```
[MAKER] Step 4 failed after 3 retries.
[MAKER] Rolling back to checkpoint ckpt-task123-step-4...
  Restored: src/utils/helper.ts
  Deleted: src/newfile.ts (created by failed step)
[MAKER] Rollback complete. File system restored to pre-step state.
[MAKER]
[MAKER] The step "Add validation function" could not be completed.
[MAKER] Options:
  1. Revise the decomposition for this step
  2. Provide additional context or clarification
  3. Skip this step and continue (may cause issues)
```

---

## Troubleshooting

### "Checkpoint not found"

**Cause**: The checkpoint metadata file is missing or corrupted.

**Solutions**:
1. Check if `.maker-checkpoints/metadata/` directory exists
2. Verify the checkpoint ID matches an existing metadata file
3. If using git strategy, check `git stash list` for the checkpoint stash

### "Restore failed: file conflict"

**Cause**: A file was modified externally while checkpoint exists.

**Solutions**:
1. Review the conflicting file manually
2. Use `git checkout --theirs {file}` to prefer checkpoint version
3. Create a new checkpoint and retry the operation

### "Cannot create checkpoint: permission denied"

**Cause**: No write permission to `.maker-checkpoints/` directory.

**Solutions**:
1. Ensure write permission on the working directory
2. Check if `.maker-checkpoints/` is excluded by file permissions
3. Try running with elevated permissions if appropriate

### Checkpoints consuming too much space

**Cause**: Many checkpoints accumulated from long-running or failed pipelines.

**Solutions**:
1. Run `CLEANUP` operation with `CLEANUP_ALL` mode
2. Delete `.maker-checkpoints/files/` directory manually
3. If using git, run `git stash clear` (removes ALL stashes, not just MAKER's)

### Rollback didn't restore expected state

**Cause**: Checkpoint was created after some modifications, or files were not included.

**Solutions**:
1. Check checkpoint metadata to see which files were captured
2. Verify the checkpoint was created at the right point in the pipeline
3. For future runs, ensure all modified files are listed in decomposition Output fields

---

## Best Practices

1. **Let checkpoints run automatically** - The overhead is minimal and recovery is valuable
2. **Don't modify files manually during pipeline execution** - This can cause state mismatch
3. **Review rollback messages carefully** - They indicate what was restored/deleted
4. **Clean up after successful pipelines** - Prevents storage accumulation
5. **Use git-based projects when possible** - Git strategy is faster and more reliable

---

## Technical Details

### Checkpoint Metadata Schema

```json
{
  "checkpoint_id": "ckpt-task123-step-4",
  "created_at": "2025-01-22T10:30:00Z",
  "task_id": "task123",
  "step_number": 4,
  "step_name": "Add validation function",
  "strategy": "git",
  "files": [
    {
      "path": "src/utils/validator.ts",
      "exists_at_checkpoint": true,
      "stash_ref": "stash@{0}"
    },
    {
      "path": "src/utils/errors.ts",
      "exists_at_checkpoint": false
    }
  ]
}
```

### Storage Location

All checkpoint data is stored in the `.maker-checkpoints/` directory:

```
.maker-checkpoints/
  metadata/           # JSON metadata for each checkpoint
  files/              # File copies (file-copy strategy only)
```

This directory should be added to `.gitignore` if you don't want checkpoint data tracked.

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main orchestration documentation
- [maker-checkpoint-manager.md](../subagents/maker-checkpoint-manager.md) - Checkpoint manager subagent
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - General troubleshooting guide
