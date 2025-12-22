---
description: Execute MAKER pipeline - decomposes complex tasks into atomic steps and executes them
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
argument-hint: <task-description>
---

# MAKER Pipeline Command

Execute the full MAKER (Massively Decomposed Agentic Processes) pipeline.

## Process

1. Analyze the task: $ARGUMENTS
2. Use maker-complexity-estimator agent to assess task complexity
3. Use maker-decomposition agent to break into atomic steps
4. Use maker-decomposition-discriminator to validate decomposition
5. Execute each step using maker-solver agent
6. Validate each step with maker-red-flag agent
7. For critical steps, use maker-solution-discriminator for voting
8. Use maker-reviewer for final validation

## Execution Rules

- Execute steps sequentially unless parallel opportunities identified
- Use maker-parallel-coordinator to identify parallelizable steps
- Create checkpoints after each successful step using maker-checkpoint-manager
- On failure, invoke maker-red-flag agent for analysis
- Cache successful patterns using maker-cache-manager for future use
- Loop back and fix any issues identified by maker-reviewer

## Progress Reporting

Provide brief progress updates:
```
[MAKER] Decomposing task...
[MAKER] 6 steps identified, validating...
[MAKER] Approved. Executing step 1/6...
[MAKER] Step 1 complete. Executing step 2/6...
...
[MAKER] All steps complete. Running final review...
[MAKER] DONE.
```

## Output

Final summary includes:
- Steps completed
- Files created/modified
- Any issues encountered and how they were resolved
