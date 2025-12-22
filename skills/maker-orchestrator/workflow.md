# MAKER Workflow Reference

## Agent Execution Order

```
+-------------------------------------------------------------+
|                    USER REQUEST                              |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              maker-complexity-estimator                      |
|         Assess if MAKER pipeline is needed                   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                maker-decomposition                           |
|            Break into atomic steps                           |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|          maker-decomposition-discriminator                   |
|           Validate decomposition quality                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|             maker-parallel-coordinator                       |
|      Identify parallelizable step groups                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   FOR EACH STEP:                             |
|  +-------------+    +----------------------------------+    |
|  |maker-solver |----> maker-red-flag                   |    |
|  +-------------+    +----------------------------------+    |
|         |                        |                           |
|         | (on failure)           |                           |
|         v                        |                           |
|  +--------------+                |                           |
|  | RETRY (3x)   |                |                           |
|  +--------------+                |                           |
|         |                        |                           |
|         | (critical step)        |                           |
|         v                        |                           |
|  +---------------------------+   |                           |
|  |maker-solution-discriminator|  |                           |
|  +---------------------------+   |                           |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   maker-reviewer                             |
|              Final validation pass                           |
+-------------------------------------------------------------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
      [APPROVED]                      [NEEDS_FIXES]
         DONE                              |
                                          v
                              +------------------------+
                              | Fix each issue         |
                              | Re-run maker-reviewer  |
                              | Loop until APPROVED    |
                              +------------------------+
```

## Parallel Execution

When steps are independent, maker-parallel-coordinator manages concurrent execution:

```
+-------------------------------------------------------------+
|                      WAVE 1                                  |
|                    [Step 001]                                |
|                    Sequential                                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      WAVE 2                                  |
|           [Step 002]    [Step 003]                           |
|           Parallel      Parallel                             |
|           (run_in_background: true)                          |
+-------------------------------------------------------------+
                              |
                     Collect results
                              |
                              v
+-------------------------------------------------------------+
|                      WAVE 3                                  |
|                    [Step 004]                                |
|              Depends on 002 and 003                          |
+-------------------------------------------------------------+
```

## Checkpoint Flow

```
FOR each step:
  1. maker-checkpoint-manager CREATE (before step)
  2. maker-solver (execute step)
  3. maker-red-flag (validate)
  4. IF valid: continue to next step
  5. IF invalid: RETRY up to 3x
  6. IF still invalid: maker-checkpoint-manager RESTORE

ON pipeline success:
  maker-checkpoint-manager CLEANUP (RETAIN_LAST: 1)

ON pipeline failure:
  maker-checkpoint-manager RESTORE (latest good checkpoint)
```

## Cache Flow

```
BEFORE decomposition:
  maker-cache-manager LOOKUP
  IF CACHE_HIT:
    Use cached decomposition with adaptation
  IF CACHE_MISS:
    Proceed with fresh decomposition

AFTER successful pipeline:
  maker-cache-manager STORE
  Save decomposition for future reuse

ON cache too old (30 days):
  maker-cache-manager INVALIDATE (STALE)

ON repeated failures (3+):
  maker-cache-manager INVALIDATE (FAILED)
```

## Review Loop

```
maker-reviewer
    |
    +-> [APPROVED] -> DONE
    |
    +-> [NEEDS_FIXES]
            |
            v
        FOR each issue (priority order):
            1. Create fix step
            2. maker-solver (fix)
            3. maker-red-flag (validate fix)
            |
            v
        Re-run maker-reviewer
            |
            +-> Loop until [APPROVED]
            |
            +-> Max 3 review cycles, then escalate to user
```
