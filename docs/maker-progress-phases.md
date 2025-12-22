# MAKER Progress Phases Reference

## Purpose

This document defines the progress phases displayed during MAKER solver execution. The orchestrator uses these phase definitions to provide users with meaningful, contextual progress updates as each step executes.

Progress phases transform opaque solver execution into transparent, informative feedback that helps users understand what is happening without overwhelming them with internal details.

---

## Phase Definitions

### Action Type to Phases Mapping

| Action Type | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-------------|---------|---------|---------|---------|
| **Create File** | Preparing structure... | Writing file... | Verifying creation... | - |
| **Modify File** | Reading existing file... | Applying changes... | Writing updates... | Verifying changes... |
| **Read/Analyze** | Scanning files... | Analyzing content... | Extracting information... | - |
| **Execute Command** | Preparing command... | Running command... | Processing output... | - |
| **Verify/Test** | Setting up verification... | Running checks... | Validating results... | - |

### Phase Details

**Create File (3 phases)**
1. `Preparing structure...` - Determining file location and initial content
2. `Writing file...` - Creating the file with specified content
3. `Verifying creation...` - Confirming file exists and is valid

**Modify File (4 phases)**
1. `Reading existing file...` - Loading current file content
2. `Applying changes...` - Processing the required modifications
3. `Writing updates...` - Saving the modified content
4. `Verifying changes...` - Confirming modifications were applied correctly

**Read/Analyze (3 phases)**
1. `Scanning files...` - Locating and accessing target files
2. `Analyzing content...` - Processing file contents
3. `Extracting information...` - Gathering required data

**Execute Command (3 phases)**
1. `Preparing command...` - Setting up execution environment
2. `Running command...` - Executing the command
3. `Processing output...` - Capturing and interpreting results

**Verify/Test (3 phases)**
1. `Setting up verification...` - Preparing test conditions
2. `Running checks...` - Executing validation steps
3. `Validating results...` - Confirming expected outcomes

---

## Phase Detection Guidance

### Action Type Detection

The orchestrator determines action type by matching keywords in the step's ACTION field:

| Keywords | Action Type |
|----------|-------------|
| `create`, `add`, `write`, `generate`, `initialize` | Create File |
| `modify`, `update`, `edit`, `change`, `fix`, `refactor` | Modify File |
| `read`, `analyze`, `scan`, `inspect`, `examine`, `extract` | Read/Analyze |
| `run`, `execute`, `install`, `build`, `test`, `deploy` | Execute Command |
| `verify`, `validate`, `check`, `confirm`, `ensure`, `test` | Verify/Test |

**Priority:** If multiple keywords match, use this priority order:
1. Execute Command (if `run`, `execute`, `install`, `build` present)
2. Verify/Test (if `verify`, `validate`, `check` present)
3. Modify File (if `modify`, `update`, `edit` present)
4. Create File (if `create`, `add`, `write` present)
5. Read/Analyze (fallback for analysis-only actions)

**Note:** The keyword `test` appears in both Execute Command and Verify/Test. When `test` is the only matching keyword, it resolves to Execute Command due to priority rules (e.g., "run the test suite"). Verify/Test is selected when verification-specific keywords like `verify`, `validate`, or `check` are also present.

### Emission Format

Progress phases are emitted during solver execution using this format:

```
[MAKER] Executing step {N}/{Total}: {step_name}...
  [{N}/{Total}] {phase_1_message}
  [{N}/{Total}] {phase_2_message}
  [{N}/{Total}] {phase_3_message}
  [{N}/{Total}] {phase_4_message}   (if applicable)
```

**Example - Create File action:**
```
[MAKER] Executing step 1/6: Create user model...
  [1/6] Preparing structure...
  [1/6] Writing file...
  [1/6] Verifying creation...
```

**Example - Modify File action:**
```
[MAKER] Executing step 3/6: Add validation to handler...
  [3/6] Reading existing file...
  [3/6] Applying changes...
  [3/6] Writing updates...
  [3/6] Verifying changes...
```

### Timing Guidelines

- Emit each phase as the solver enters that logical stage
- Phases should reflect actual work, not artificial delays
- If a phase completes instantly, still emit it for consistency
