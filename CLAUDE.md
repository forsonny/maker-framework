# MAKER Framework Plugin

## CRITICAL: Solver Delegation Requirement

**The orchestrator MUST NOT execute step actions directly.**

When executing steps in the MAKER pipeline:
1. Use the `Task` tool with `subagent_type: "maker-framework:maker-solver"`
2. Pass the step details via the prompt parameter
3. Let the solver agent perform all file operations (Read, Write, Edit, Bash)

**NEVER do this (WRONG):**
```
[MAKER] Executing step 1/6: Create config file...
<orchestrator directly calls Write tool>
```

**ALWAYS do this (CORRECT):**
```
[MAKER] Executing step 1/6: Create config file...
<orchestrator calls Task tool with subagent_type="maker-framework:maker-solver">
```

**If you find yourself about to use Write, Edit, or Bash directly during step execution - STOP. Use the Task tool to spawn a maker-solver instead.**

## Subagent Names (Fully Qualified)

All subagent invocations MUST use the `maker-framework:` prefix:
- `maker-framework:maker-solver`
- `maker-framework:maker-decomposition`
- `maker-framework:maker-decomposition-discriminator`
- `maker-framework:maker-red-flag`
- `maker-framework:maker-reviewer`
- `maker-framework:maker-solution-discriminator`
- `maker-framework:maker-complexity-estimator`
- `maker-framework:maker-checkpoint-manager`
- `maker-framework:maker-cache-manager`
- `maker-framework:maker-parallel-coordinator`

## Detailed Documentation

For detailed orchestration logic, see:
- Orchestrator skill: `skills/maker-orchestrator/`
- Prompt templates: `skills/maker-orchestrator/prompts.md`
- Agent definitions: `agents/`
