---
description: Execute MAKER pipeline - decomposes complex tasks into atomic steps and executes them
allowed-tools: Read, Glob, Grep
argument-hint: <task-description>
---

# MAKER Pipeline Command

Execute the full MAKER (Massively Decomposed Agentic Processes) pipeline.

## CRITICAL: Orchestration Only

**YOU (the orchestrator) MUST NOT write, edit, or execute files directly.**

All file operations MUST happen through the maker-solver subagent. Your role is STRICTLY to:
1. Invoke subagents via the Task tool
2. Pass state between steps
3. Handle validation and retry logic
4. Report progress

**FORBIDDEN ACTIONS for the orchestrator:**
- Using Write tool directly
- Using Edit tool directly
- Using Bash for file operations
- Creating any files yourself
- Modifying any files yourself

**If you find yourself about to write a file, STOP and invoke maker-solver instead.**

## Process

1. Analyze the task: $ARGUMENTS
2. Use Task tool with `subagent_type: "maker-framework:maker-complexity-estimator"` to assess complexity
3. Use Task tool with `subagent_type: "maker-framework:maker-decomposition"` to break into atomic steps
4. Use Task tool with `subagent_type: "maker-framework:maker-decomposition-discriminator"` to validate
5. FOR EACH STEP in the decomposition:
   a. Use Task tool with `subagent_type: "maker-framework:maker-solver"` to execute the step
   b. Use Task tool with `subagent_type: "maker-framework:maker-red-flag"` to validate output
   c. Retry up to 3x if flagged
6. For critical steps, use Task tool with `subagent_type: "maker-framework:maker-solution-discriminator"` for voting
7. Use Task tool with `subagent_type: "maker-framework:maker-reviewer"` for final validation
8. Loop back and fix any issues using maker-solver, NOT direct edits

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
[MAKER] Approved. Executing step 1/6 via maker-solver...
[MAKER] Step 1 complete. Executing step 2/6 via maker-solver...
...
[MAKER] All steps complete. Running final review...
[MAKER] DONE.
```

## Output

Final summary includes:
- Steps completed
- Files created/modified (by maker-solver, not directly)
- Any issues encountered and how they were resolved
