"""
Shared constants for QA MCP Server.

This module centralizes magic numbers and configuration constants
used across the QA MCP Server components. Each constant is documented
with its purpose and typical usage.
"""

# =============================================================================
# Coverage Reporting Limits
# =============================================================================

MAX_UNCOVERED_LINES_PER_FILE = 50
"""Maximum uncovered lines to report per source file.

Limits the number of uncovered line entries returned for any single file
to prevent overwhelming output. Coverage tools may report hundreds of
uncovered lines for a single large file; this limit ensures responses
remain manageable.

Used by: pytest_adapter, unittest_adapter
"""

MAX_UNCOVERED_LINES_TOTAL = 100
"""Maximum total uncovered lines across all files.

Hard limit on the total number of uncovered line entries in a coverage
report. Prevents extremely large responses when many files have low
coverage.

Used by: pytest_adapter, unittest_adapter, jest_adapter, mocha_adapter
"""

# =============================================================================
# Test Generation Limits
# =============================================================================

DEFAULT_MAX_FILES = 20
"""Default maximum files to process in generate_tests.

Limits auto-discovery of source files to prevent runaway processing
in large codebases. Users can override via max_files parameter.

Used by: generate_tests tool
"""

# =============================================================================
# Execution Timeouts
# =============================================================================

TOOL_TIMEOUT_SECONDS = 300
"""Default timeout for tool execution (5 minutes).

Maximum time a tool can run before being terminated. Prevents
hanging operations from blocking the server indefinitely.

Used by: server.py tool execution
"""

DEFAULT_TEST_TIMEOUT_SECONDS = 300
"""Default timeout for test execution (5 minutes).

Maximum time test suites can run before timeout. Can be
overridden via TestConfig.timeout_seconds.

Used by: all test adapters
"""

DEFAULT_COVERAGE_TIMEOUT_SECONDS = 300
"""Default timeout for coverage collection (5 minutes).

Maximum time coverage analysis can run. Coverage collection
typically takes longer than plain test execution.

Used by: all test adapters (coverage methods)
"""

HOOK_TIMEOUT_SECONDS = 60
"""Default timeout for pre/post test hooks (1 minute).

Maximum time each individual hook command can run before being
terminated. Hooks are shell commands executed before or after
test runs (e.g., database reset, cleanup).

Used by: BaseAdapter._run_hooks
"""

# =============================================================================
# Configuration Defaults
# =============================================================================

DEFAULT_COVERAGE_THRESHOLD = 70.0
"""Default coverage threshold percentage (70%).

Minimum coverage percentage required for meets_threshold to be True.
Can be overridden via CoverageConfig.threshold or qa-config.yaml.

Used by: coverage tools, maker-reviewer Check 8
"""

DEFAULT_REPORTS_DIR = "qa-reports"
"""Default directory for QA reports.

Where baseline files and other QA artifacts are stored.

Used by: check_regressions tool
"""
