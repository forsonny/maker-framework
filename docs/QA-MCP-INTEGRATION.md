# QA MCP Integration for MAKER Framework

## Overview

This document describes the integration of the QA MCP server with the MAKER framework's review phase. The QA MCP server enables automated test execution, coverage validation, and regression checking during the final review gate.

**Purpose:** Extend maker-reviewer with automated QA capabilities to catch code quality issues before approval.

**Expected Benefit:** Automated test pass rate reported in reviews, reducing manual verification effort.

---

## Available QA Tools

The QA MCP server provides the following tools when configured:

### run_tests
Executes the test suite for the project.
- **Input:** Test configuration (optional), specific test files/patterns (optional)
- **Output:** Test results including pass/fail counts, failure details, execution time
- **Use Case:** Verify all tests pass after MAKER pipeline completes work

### get_coverage
Retrieves code coverage metrics for the project.
- **Input:** Coverage configuration (optional), source file patterns (optional)
- **Output:** Coverage percentage, uncovered lines, coverage report
- **Use Case:** Ensure new code has adequate test coverage

### check_regressions
Compares current test results against a baseline.
- **Input:** Baseline reference (optional), comparison scope (optional)
- **Output:** List of regressions (newly failing tests), new passes, unchanged results
- **Use Case:** Detect if MAKER pipeline changes broke existing functionality

### generate_tests
Generates test cases for new or modified code.
- **Input:** Source files to test, test framework preference
- **Output:** Generated test file content
- **Use Case:** Automatically create tests for new functionality added by MAKER

### ping
Verifies the QA MCP server is running and responsive.
- **Input:** None (empty object `{}`)
- **Output:** Server status, name, and version
- **Use Case:** Health check before running other QA tools

### check_prd_alignment
Verifies implementation code aligns with Product Requirements Document (PRD).
- **Input:**
  - `prd_path` (required): Path to PRD file (markdown, txt, or text format)
  - `implementation_paths` (optional): List of implementation file paths
  - `working_dir` (optional): Working directory for file discovery
  - `requirement_patterns` (optional): Custom regex patterns to extract requirements
- **Output:**
  - `alignment_score`: 0-100 alignment percentage
  - `matched_requirements`: List of requirements found in implementation
  - `unmatched_requirements`: List of requirements not addressed
  - `recommendations`: Suggestions for improving alignment
- **Use Case:** Validate MAKER pipeline output meets original requirements during decomposition validation and final review

### aggregate_qa_report
Aggregates QA results from multiple validation stages into a unified report.
- **Input:**
  - `stage_results` (required): List of stage result objects with:
    - `stage_name`: Name of the validation stage
    - `passed`: Number of passed checks
    - `failed`: Number of failed checks
    - `details`: Stage-specific details (coverage %, regressions, etc.)
  - `include_summary` (optional): Include summary statistics (default: true)
  - `format` (optional): Output format - "full", "compact", or "summary_only"
- **Output:**
  - `summary`: Aggregate statistics (total_passed, total_failed, pass_rate)
  - `stages`: List of processed stage results
  - `overall_status`: PASS, FAIL, or PARTIAL
  - `recommendations`: List of improvement suggestions
  - `timestamp`: ISO timestamp of report generation
- **Use Case:** Generate unified QA report in maker-reviewer Check 9 after all QA checks complete


**Note:** This is a registered MCP tool and can be called via `tools/call` like any other tool.

Example via tools/call:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ping","arguments":{}}}' | python -m qa_server
```

Example via direct JSON-RPC method:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | python -m qa_server
```

---

## Integration with maker-reviewer

The maker-reviewer agent uses QA MCP tools during **Check 8: QA Engine Validation**.

### When QA Tools Are Invoked

1. **After Check 7 (Run Tests):** If QA MCP is configured, maker-reviewer invokes QA tools
2. **Conditional Execution:** QA checks are SKIPPED if:
   - No test files exist in the project
   - QA MCP server is not configured
   - Task explicitly marked as "no-tests"

### Issue Reporting

If QA checks fail, maker-reviewer reports issues in standard format:

\`\`\`
[ISSUE N] QA Engine - Test Failures
  Severity: HIGH
  Location: Test suite
  Description: X tests failed out of Y total
  Evidence: [List of failing test names]
  Required Fix: Fix failing tests or update test expectations
\`\`\`

---

## Configuration

### Step 1: Create MCP Configuration

Create or update \`.mcp.json\` in the project root:

\`\`\`json
{
  "mcpServers": {
    "claude-qa": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "qa_server"]
    }
  }
}
\`\`\`

### Step 2: Install QA Server

The QA server is included in the MAKER framework. Ensure dependencies are installed:

\`\`\`bash
# Install Python dependencies
pip install pyyaml

# For test framework support:
pip install pytest pytest-json-report coverage  # For Python projects
\`\`\`

### Step 3: Verify Configuration

Test that the MCP server starts correctly:

\`\`\`bash
cd maker-framework
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python -m qa_server
\`\`\`

### Environment Requirements

- Python 3.8+ required
- PyYAML package
- Test framework (pytest, Jest, Mocha, unittest)

### Pre/Post Test Hooks

You can configure shell commands to run before and after test execution using `pre_hooks` and `post_hooks` in your `qa-config.yaml`:

\`\`\`yaml
test:
  pre_hooks:
    - "docker-compose up -d db"        # Start database container
    - "python manage.py migrate"        # Run migrations
  post_hooks:
    - "docker-compose down"             # Stop containers
    - "rm -rf tmp/"                     # Clean up temp files
\`\`\`

**Hook Behavior:**
- Pre-hooks run sequentially before test execution
- If any pre-hook fails, tests are not executed and an error is returned
- Post-hooks run after tests complete (regardless of test outcome)
- Post-hook failures are logged as warnings but do not affect test results
- Hooks run with `shell=True` in the working directory
- Hook commands are sanitized to prevent shell injection (dangerous characters filtered)

**Adapter Support:**
- pytest: Full hook support, full regression tracking (passed test names collected)
- Jest: Full hook support, full regression tracking (passed test names collected)
- Mocha: Full hook support, full regression tracking (passed test names collected)
- unittest: Full hook support, limited regression tracking (only detects new failures; passed test names not collected)

---

## Troubleshooting

### QA Tools Not Available

**Symptom:** maker-reviewer reports "Check 8: SKIPPED - QA MCP not configured"

**Solution:**
1. Verify \`.mcp.json\` exists and is valid JSON
2. Check that Python and qa_server module are available
3. Restart Claude Code to reload MCP configuration

### Tests Fail to Run

**Symptom:** run_tests returns error instead of results

**Solution:**
1. Verify test framework is installed
2. Check test configuration file exists
3. Run tests manually to verify they work

### Limitations

#### Platform-Specific Limitations (Windows)

The QA MCP Server has the following limitations on Windows:

1. **Configuration Reload:** On Unix/Linux, the server reloads configuration when receiving SIGHUP signal. On Windows, SIGHUP is not available - you must restart the server to pick up configuration changes.

2. **Signal Handling:** Only SIGINT (Ctrl+C) is available for graceful shutdown on Windows. SIGTERM and SIGHUP are Unix-only.

**Workaround:** Restart the QA MCP server after modifying `qa-config.yaml` on Windows systems.

#### Batch Requests Not Supported

The QA MCP Server does not support JSON-RPC 2.0 batch requests (sending multiple requests in a JSON array). Each request must be sent individually.

**Example of unsupported format:**
```json
[
  {"jsonrpc":"2.0","id":1,"method":"ping","params":{}},
  {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
]
```

**Supported format:** Send requests one at a time:
```json
{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
```

#### Tool Timeout Behavior

When a tool exceeds the configured timeout (default: 300 seconds), the server:
1. Returns a TIMEOUT_ERROR response immediately
2. Sets the cancellation token to signal the tool should stop
3. Logs a warning that the daemon thread may still be running

**Note:** The underlying tool operation may continue running in the background until it completes or checks its cancellation token. Tools should periodically check `cancellation_token.is_cancelled()` during long-running operations for graceful cancellation.

#### Watch Mode Not Supported
The QA MCP Server operates in request-response mode only. Watch mode (automatic re-run on file changes) is not currently supported. Tests must be explicitly triggered via tool calls.

#### Coverage Source and Exclude Patterns
The `coverage.source_patterns` and `coverage.exclude_patterns` configuration fields control which files are included in coverage measurement:

```yaml
coverage:
  source_patterns:         # Files to include in coverage
    - "src/**/*.py"
    - "lib/**/*.py"
  exclude_patterns:        # Files to exclude from coverage
    - "**/test/**"
    - "**/__pycache__/**"
```

**Framework-specific behavior:**
- **pytest/unittest** (coverage.py): `source_patterns` extracts base directories for `--source` arguments; `exclude_patterns` maps to `--omit`
- **Jest**: Both patterns map to `--collectCoverageFrom` (exclusions use `!` prefix)
- **Mocha** (nyc): `source_patterns` maps to `--include`; `exclude_patterns` maps to `--exclude`

#### Parallel Execution
Parallel test execution (via the `parallel` config option) is only supported for pytest (requires pytest-xdist). Jest and Mocha adapters ignore this setting.

### Regression Tracking Limitations

When using text output parsing (non-JSON test reports), the `passed_names` field in test results will be empty. This affects the accuracy of regression detection.

**Affected Adapters:**
- **unittest**: Always uses text output parsing; `passed_names` is never populated
- **pytest** (without JSON plugin): Falls back to text parsing when `pytest-json-report` is not installed

**Impact on Regression Detection:**
- `check_regressions` can only detect newly failing tests (tests that passed before but fail now)
- Cannot detect "fixed" tests (tests that failed before but pass now) when `passed_names` is empty
- Regression reports may be incomplete without full pass/fail history

**How to Enable Full Regression Tracking:**

For **pytest**, install the JSON report plugin:
```bash
pip install pytest-json-report
```

For **Jest** and **Mocha**, JSON output is enabled by default - no additional configuration needed.

For **unittest**, consider migrating to pytest for full regression tracking support, or accept that only failure-based regression detection is available.

---

## Error Codes

The QA MCP Server uses standard JSON-RPC 2.0 error codes plus custom codes:

| Code | Name | Description |
|------|------|-------------|
| -32700 | PARSE_ERROR | Invalid JSON or message too large |
| -32600 | INVALID_REQUEST | Invalid JSON-RPC request |
| -32601 | METHOD_NOT_FOUND | Unknown method |
| -32602 | INVALID_PARAMS | Invalid tool parameters |
| -32603 | INTERNAL_ERROR | Server internal error |

### Tool-Specific Error Codes

Tool results may include these error codes in the response:

| Code | Description |
|------|-------------|
| TIMEOUT_ERROR | Tool execution exceeded timeout |
| CANCELLED | Request was cancelled by client |
| TOOL_ERROR | General tool execution error |

---


---

## Multi-Stage QA Integration

The QA MCP tools integrate at multiple stages of the MAKER pipeline for comprehensive quality assurance:

### Stage 1: Decomposition Validation (maker-decomposition-discriminator)

During decomposition validation, the discriminator can invoke `check_prd_alignment` to verify the planned implementation will satisfy requirements:

**When Used:**
- Original task references a PRD or requirements document
- Task involves implementing features from specifications

**How It Works:**
1. Discriminator detects PRD reference in task context
2. Invokes `mcp__claude-qa__check_prd_alignment` with PRD path
3. Reports alignment score in Testability Check (Check 6)
4. Flags low alignment (<70%) as issue requiring revision

### Stage 2: Final Review (maker-reviewer)

The reviewer uses all QA tools during Checks 7-9:

**Check 7: Tests**
- Runs tests using Bash tool directly

**Check 8: QA Engine Validation**
- `run_tests`: Execute test suite via MCP
- `get_coverage`: Validate coverage threshold
- `check_regressions`: Detect broken tests
- `generate_tests`: Create tests for new code (if applicable)
- `check_prd_alignment`: Verify final implementation meets requirements

**Check 9: Unified QA Report**
- `aggregate_qa_report`: Combine all QA stage results
- Generate overall status (PASS/FAIL/PARTIAL)
- Produce actionable recommendations

### Cross-Stage Data Flow

```
Decomposition Phase
    |
    +-- check_prd_alignment --> alignment_score
    |
    v
Execution Phase
    |
    v
Review Phase
    |
    +-- run_tests -----------> test_results
    +-- get_coverage --------> coverage_results
    +-- check_regressions ---> regression_results
    +-- check_prd_alignment -> final_alignment
    |
    v
aggregate_qa_report
    |
    +-- Combine all results
    +-- Calculate overall status
    +-- Generate recommendations
    |
    v
UNIFIED QA REPORT
```

### Configuration for Multi-Stage

Ensure all stages can access QA tools by configuring `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "claude-qa": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "qa_server"],
      "cwd": "path/to/maker-framework"
    }
  }
}
```

### Success Metrics

With full QA suite integration, the MAKER pipeline reports:

- **PRD Alignment Score**: How well implementation matches requirements
- **Test Pass Rate**: Percentage of passing tests
- **Coverage Percentage**: Code coverage level
- **Regression Count**: Number of newly broken tests
- **Overall QA Status**: Aggregated PASS/FAIL/PARTIAL verdict

## References

- MAKER Framework: [CLAUDE.md](../CLAUDE.md)
- maker-reviewer Agent: [subagents/maker-reviewer.md](../subagents/maker-reviewer.md)
- maker-decomposition-discriminator Agent: [subagents/maker-decomposition-discriminator.md](../subagents/maker-decomposition-discriminator.md)
- MAKER Paper: arXiv:2511.09030
