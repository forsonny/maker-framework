"""
Type definitions for QA MCP Server results.

These TypedDicts define the JSON structure returned by QA tools,
designed to be compatible with maker-reviewer's Check 8 expectations.

Expected formats per QA-MCP-INTEGRATION.md:
- TestResult: { "passed": N, "failed": M, "total": X, "failures": [...], "duration_ms": N }
- CoverageResult: { "percentage": N, "uncovered_lines": [...], "meets_threshold": bool }
- RegressionResult: { "regressions": [...], "new_passes": [...], "unchanged": N }
"""

from typing import List, Optional, Any, Literal

# TypedDict was added to typing in Python 3.8
# NotRequired was added in Python 3.11
# Use typing_extensions for compatibility with older versions
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class QAUnavailableResult(TypedDict):
    """An unavailable QA check, distinct from passing or failing product tests."""
    status: Literal["unavailable"]
    code: Literal["NO_SUPPORTED_TEST_FRAMEWORK"]
    message: str
    tests_executed: int


class TestFailure(TypedDict):
    """Details of a single test failure."""
    name: str
    message: str
    file: Optional[str]
    line: Optional[int]


class TestResult(TypedDict):
    """Result of running tests via run_tests tool.

    Compatible with maker-reviewer Check 8 expectations:
    - passed: Number of passing tests
    - failed: Number of failing tests
    - total: Total number of tests
    - failures: List of failure details
    - duration_ms: Execution time in milliseconds
    - passed_names: Optional list of passing test names (for regression tracking)
    """
    passed: int
    failed: int
    total: int
    failures: List[TestFailure]
    duration_ms: int
    passed_names: NotRequired[List[str]]


class UncoveredLine(TypedDict):
    """Details of an uncovered line of code."""
    file: str
    line: int
    content: Optional[str]


class CoverageResult(TypedDict):
    """Result of coverage analysis via get_coverage tool.

    Compatible with maker-reviewer Check 8 expectations:
    - percentage: Coverage percentage (0-100), or None when unavailable
    - uncovered_lines: List of lines not covered by tests
    - meets_threshold: Whether coverage meets the configured threshold
    """
    percentage: Optional[float]
    uncovered_lines: List[UncoveredLine]
    meets_threshold: bool


class RegressionItem(TypedDict):
    """Details of a test regression."""
    name: str
    previous_status: str  # "PASS" or "SKIP"
    current_status: str   # "FAIL"
    message: Optional[str]


class NewPassItem(TypedDict):
    """Details of a newly passing test."""
    name: str
    previous_status: str  # "FAIL" or "SKIP"
    current_status: str   # "PASS"


class NewTestItem(TypedDict):
    """Details of a newly added test (not in baseline)."""
    name: str
    current_status: str   # "PASS" or "FAIL"


class MissingTestItem(TypedDict):
    """Details of a test that existed in baseline but is missing from current results."""
    name: str
    previous_status: str  # Status in baseline ("PASS", "FAIL", or "SKIP")
    message: str          # Explanation of why this may be missing


class RegressionResult(TypedDict):
    """Result of regression check via check_regressions tool.

    Compatible with maker-reviewer Check 8 expectations:
    - regressions: Tests that previously passed but now fail
    - new_passes: Tests that previously failed but now pass
    - unchanged: Count of tests with unchanged status
    - new_tests: Tests that weren't in the baseline (newly added)
    - missing_tests: Tests in baseline but not in current results (deleted/renamed)
    """
    regressions: List[RegressionItem]
    new_passes: List[NewPassItem]
    unchanged: int
    new_tests: NotRequired[List[NewTestItem]]
    missing_tests: NotRequired[List[MissingTestItem]]  # Tests in baseline but missing from current


class GeneratedTestFile(TypedDict):
    """Details of a single generated test file."""
    source: str
    test_file: NotRequired[str]  # May not exist if generation failed
    content: NotRequired[str]    # May not exist if generation failed
    test_count: NotRequired[int] # May not exist if generation failed
    written: bool
    write_error: NotRequired[str]
    error: NotRequired[str]      # For generation errors (not write errors)


class GenerateTestsResult(TypedDict):
    """Result of test generation via generate_tests tool."""
    generated_files: List[GeneratedTestFile]
    framework: str
    total_tests: int
    error: NotRequired[str]