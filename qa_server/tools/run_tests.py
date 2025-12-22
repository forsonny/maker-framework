"""
run_tests tool implementation for QA MCP Server.

Executes tests using the appropriate test framework adapter
and returns structured results compatible with maker-reviewer.
"""

from typing import Dict, Any, Optional
import os

from ..types import TestResult
from ..config import QAConfig, load_config, sanitize_extra_args
from ..adapter_factory import get_adapter
from ..utils import validate_working_dir


# MCP Tool Schema for run_tests
RUN_TESTS_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Glob pattern to filter tests (e.g., 'test_*.py', '**/*.test.js')",
        },
        "framework": {
            "type": "string",
            "description": "Test framework to use (pytest, jest, mocha, unittest, or 'auto' for detection)",
            "enum": ["auto", "pytest", "jest", "mocha", "unittest"],
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds for test execution",
            "minimum": 1,
            "maximum": 3600,
        },
        "working_dir": {
            "type": "string",
            "description": "Working directory for test execution (defaults to current directory)",
        },
        "extra_args": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Additional arguments to pass to the test framework. "
                "SECURITY: Arguments are sanitized to prevent command injection - "
                "arguments containing shell metacharacters (;|&$`(){}<>) will be rejected."
            ),
        },
    },
    "additionalProperties": False,
}

RUN_TESTS_DESCRIPTION = """Execute test suite and return results.

Runs tests using the detected or specified test framework (pytest, jest, mocha, unittest).
Returns structured results with pass/fail counts and failure details.

Compatible with maker-reviewer Check 8 QA validation."""


def run_tests_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle run_tests tool invocation.

    Args:
        arguments: Tool arguments from MCP call
            - pattern: Optional test file pattern
            - framework: Optional framework override
            - timeout: Optional timeout in seconds
            - working_dir: Optional working directory
            - extra_args: Optional additional arguments (sanitized for security)

    Returns:
        TestResult dict with:
            - passed: Number of passing tests
            - failed: Number of failing tests
            - total: Total number of tests
            - failures: List of failure details
            - duration_ms: Execution time in milliseconds
    """
    # Extract arguments
    pattern = arguments.get("pattern")
    framework = arguments.get("framework", "auto")
    timeout = arguments.get("timeout")
    working_dir = arguments.get("working_dir")

    # Validate glob pattern syntax
    if pattern is not None:
        try:
            import fnmatch
            import re
            # Try to compile the pattern to check for syntax errors
            fnmatch.translate(pattern)
            # Check for dangerous pattern constructs
            if len(pattern) > 1000:  # Prevent extremely long patterns
                return TestResult(
                    passed=0,
                    failed=0,
                    total=0,
                    failures=[{
                        "name": "validation_error",
                        "message": "Pattern too long (max 1000 characters)",
                        "file": None,
                        "line": None,
                    }],
                    duration_ms=0,
                )
        except (re.error, ValueError) as e:
            return TestResult(
                passed=0,
                failed=0,
                total=0,
                failures=[{
                    "name": "validation_error",
                    "message": f"Invalid glob pattern: {e}",
                    "file": None,
                    "line": None,
                }],
                duration_ms=0,
            )

    # Validate timeout parameter
    if timeout is not None:
        try:
            timeout_val = int(timeout)
            if timeout_val <= 0:
                return TestResult(
                    passed=0,
                    failed=0,
                    total=0,
                    failures=[{
                        "name": "validation_error",
                        "message": "Invalid timeout value: must be a positive integer",
                        "file": None,
                        "line": None,
                    }],
                    duration_ms=0,
                )
            timeout = timeout_val
        except (TypeError, ValueError):
            return TestResult(
                passed=0,
                failed=0,
                total=0,
                failures=[{
                    "name": "validation_error",
                    "message": "Invalid timeout value: must be an integer",
                    "file": None,
                    "line": None,
                }],
                duration_ms=0,
            )

    # Validate working_dir using shared utility
    is_valid, validated_path, error_msg = validate_working_dir(working_dir)
    if not is_valid:
        return TestResult(
            passed=0,
            failed=0,
            total=0,
            failures=[{
                "name": "validation_error",
                "message": error_msg,
                "file": None,
                "line": None,
            }],
            duration_ms=0,
        )
    working_dir = str(validated_path) if validated_path else None

    # Load config
    config = load_config()

    # Override framework if specified
    if framework != "auto":
        config.test.framework = framework

    # Override timeout if specified
    if timeout is not None:
        config.test.timeout_seconds = timeout

    # Override extra_args if specified (sanitized for security)
    extra_args = arguments.get("extra_args")
    if extra_args is not None:
        # Type check: extra_args must be a list
        if not isinstance(extra_args, list):
            return TestResult(
                passed=0,
                failed=0,
                total=0,
                failures=[{
                    "name": "validation_error",
                    "message": f"extra_args must be a list, got {type(extra_args).__name__}",
                    "file": None,
                    "line": None,
                }],
                duration_ms=0,
            )
        config.test.extra_args = sanitize_extra_args(extra_args)

    # Get appropriate adapter
    try:
        adapter = get_adapter(config, working_dir=working_dir)
    except ValueError as e:
        return TestResult(
            passed=0,
            failed=0,
            total=0,
            failures=[{
                "name": "adapter_error",
                "message": str(e),
                "file": None,
                "line": None,
            }],
            duration_ms=0,
        )

    # Run tests
    try:
        result = adapter.run_tests(pattern=pattern, config=config.test, verbose=config.verbose)

        # Ensure result is a proper dict (TypedDict is dict subclass)
        return dict(result)

    except Exception as e:
        return dict(TestResult(
            passed=0,
            failed=0,
            total=0,
            failures=[{
                "name": "execution_error",
                "message": f"Error running tests: {e}",
                "file": None,
                "line": None,
            }],
            duration_ms=0,
        ))
