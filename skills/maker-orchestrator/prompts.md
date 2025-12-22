# MAKER Prompt Templates

## Complexity Estimation Prompt

```
[TASK]
{user_request}

[CONTEXT]
{codebase context, file paths, architectural information}

[HINTS]
{user-provided complexity hints or constraints, if any}
```

## Decomposition Prompt

```
[TASK]
{user_request}

[CONTEXT]
{relevant context about the codebase, project, or constraints}

[GRANULARITY]
target_steps: {from complexity estimator}
granularity_level: {MINIMAL | LOW | STANDARD | HIGH | MAXIMAL}
merge_trivial: {true | false}
```

## Decomposition Validation Prompt

```
[DECOMPOSITION]
{full decomposition output from maker-decomposition}

[ORIGINAL TASK]
{the original task that was decomposed}
```

## Solver Prompt

```
==========================================
MICROAGENT TASK ASSIGNMENT
==========================================

[TASK_ID]     {unique-id-for-this-task}
[STEP]        {N} of {Total}
[STEP_NAME]   {name from decomposition}

[ACTION]
{Action field from decomposition}

[INPUT_STATE]
{Output state from previous step, or initial state for step 1}

[EXPECTED_OUTPUT]
{Output field from decomposition}

[CONSTRAINTS]
{Any constraints from decomposition}

[CONTEXT]
{Any additional context needed}

==========================================
```

## Red-Flag Validation Prompt

```
[SOLVER_OUTPUT]
{complete output from maker-solver}

[EXPECTED_FORMAT]
The solver output should contain:
- [TASK_ID] field
- [STEP] field
- [STATUS] field (SUCCESS or BLOCKED)
- ACTION TAKEN section
- OUTPUT STATE section
- VERIFICATION section (if SUCCESS)
- NEXT STEP INPUT section (if SUCCESS)

[REQUIRED_FIELDS]
- TASK_ID
- STEP
- STATUS
- ACTION TAKEN
- OUTPUT STATE
```

## Retry Prompt (After Red-Flag)

```
==========================================
RETRY REQUEST - ATTEMPT {N}
==========================================

[RETRY_ATTEMPT]   {2 or 3}
[MAX_ATTEMPTS]    3
[STEP_REFERENCE]  Step {step_number} of {total_steps}: {step_name}

[PREVIOUS_FLAG_REASON]
- Primary: {main reason output was flagged}
- Secondary: {additional issues if any}

[SPECIFIC_VIOLATIONS]
- Token count: {X}/750 (if exceeded)
- Missing fields: {list of missing required fields}
- Format errors: {specific formatting issues}

[GUIDANCE]
{Specific instructions on how to fix the issues}

[RESUME_NOTE]
Your previous attempt is preserved in conversation history.
Review what you produced and apply the corrections above.
Do not restart from scratch - refine your previous output.

==========================================
```

## Voting Prompt (Critical Steps)

```
==========================================
VOTING SESSION
==========================================

[STEP_INFO]
Step Number: {N} of {Total}
Step Name: {name}
Action Required: {action}

[INPUT_STATE]
{The input state for this step}

[EXPECTED_OUTPUT]
{What the step should produce}

[CANDIDATE_COUNT] 3

------------------------------------------
CANDIDATE A
------------------------------------------
{Complete output from solver attempt 1}

------------------------------------------
CANDIDATE B
------------------------------------------
{Complete output from solver attempt 2}

------------------------------------------
CANDIDATE C
------------------------------------------
{Complete output from solver attempt 3}

==========================================
```

## Review Prompt

```
==========================================
MAKER REVIEW REQUEST
==========================================

[ORIGINAL TASK]
{The original task the user requested}

[DECOMPOSITION SUMMARY]
Total Steps: {N}
Steps Completed: {N}
Critical Steps: {list}

[COMPLETED WORK]
{Summary of what was done in each step}

Step 1: {description of what was done}
Step 2: {description of what was done}
...

[FILES CREATED/MODIFIED]
{List of all files that were created or modified}
- {file1}: {description}
- {file2}: {description}
...

[FINAL STATE]
{Description of the final state after all steps}

[REVIEW SCOPE]
- Check completeness against original task
- Check for gaps and missing functionality
- Check official documentation compliance (if applicable)
- Check code quality and error handling
- Check integration between components

==========================================
```

## Fix Step Prompt (After Review Issues)

```
==========================================
MICROAGENT TASK ASSIGNMENT
==========================================

[TASK_ID]     {original-task-id}-fix-{issue-number}
[STEP]        Fix {issue number} of {total issues}
[STEP_NAME]   Fix: {issue category}

[ACTION]
{Copy the "Required Fix" from the reviewer's issue}

[INPUT_STATE]
{Current state of the relevant file/component}
{Include the "Evidence" from the reviewer showing the problem}

[EXPECTED_OUTPUT]
{The issue should be resolved}
{Describe what "fixed" looks like}

[CONSTRAINTS]
- Only fix this specific issue
- Do not modify unrelated code
- Maintain existing functionality

[CONTEXT]
Issue from MAKER Reviewer:
{Copy the full issue description from reviewer}

==========================================
```

## Parallel Coordination Prompt

```
==========================================
PARALLEL EXECUTION PLANNING
==========================================

[DECOMPOSITION]
{The complete approved decomposition including:
 - All subtasks with Parallel: yes/no markings
 - EXECUTION ORDER section showing dependencies
 - Step dependencies listed for each subtask}

[TASK_ID]
{Unique identifier for this pipeline}

==========================================
```

## Checkpoint Create Prompt

```
==========================================
CHECKPOINT OPERATION: CREATE
==========================================

[CHECKPOINT_ID]
{unique identifier, e.g., "ckpt-001-step-3"}

[STEP_INFO]
step_number: {N}
step_name: {name of the step about to execute}
task_id: {the pipeline's task ID}

[FILES_TO_CHECKPOINT]
{List of files that will be modified by this step}
- {file_path_1}
- {file_path_2}

[WORKING_DIRECTORY]
{The working directory path}

==========================================
```

## Cache Lookup Prompt

```
==========================================
CACHE OPERATION: LOOKUP
==========================================

[TASK_SIGNATURE]
task_type: {CRUD | REFACTOR | ADD_FEATURE | MIGRATE | FIX | CONFIG | TEST | OTHER}
complexity: {MINIMAL | LOW | STANDARD | HIGH | MAXIMAL}
keywords: [{keyword1}, {keyword2}, ...]
file_patterns: [{pattern1}, {pattern2}, ...]

[TASK_DESCRIPTION]
{The full task description from the user}

[CACHE_DIRECTORY]
{Path to cache directory}

==========================================
```
