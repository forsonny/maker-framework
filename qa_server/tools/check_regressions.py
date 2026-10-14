"""
check_regressions tool implementation for QA MCP Server.

Compares current test results against a baseline to detect
regressions (tests that previously passed but now fail).
"""

import json
import logging
import os
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

from ..types import RegressionResult, RegressionItem, NewPassItem, NewTestItem, MissingTestItem
from ..config import load_config, RegressionConfig
from ..adapter_factory import get_adapter, NoSupportedFramework
from ..utils import validate_working_dir


def validate_baseline_path(
    baseline_path: str,
    working_dir: Path,
) -> tuple:
    """Validate baseline path for security (path traversal prevention).

    Args:
        baseline_path: User-provided baseline file path
        working_dir: The validated working directory

    Returns:
        Tuple of (is_valid: bool, resolved_path: Optional[Path], error_msg: Optional[str])
    """
    if not baseline_path:
        return (True, None, None)

    try:
        # Resolve the path to catch ".." traversal
        resolved = (working_dir / baseline_path).resolve()

        # Check if path is within working_dir
        try:
            resolved.relative_to(working_dir.resolve())
            return (True, resolved, None)
        except ValueError:
            # Path is outside working_dir - security violation
            return (
                False,
                None,
                f"Baseline path must be within working directory: {baseline_path}",
            )
    except (OSError, ValueError) as e:
        return (False, None, f"Invalid baseline path: {e}")


# MCP Tool Schema for check_regressions
CHECK_REGRESSIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "baseline": {
            "type": "string",
            "description": "Path to baseline JSON file (defaults to qa-reports/baseline.json)",
        },
        "update_baseline": {
            "type": "boolean",
            "description": "Update baseline with current results after comparison",
        },
        "framework": {
            "type": "string",
            "description": "Test framework to use (pytest, jest, mocha, unittest, or 'auto')",
            "enum": ["auto", "pytest", "jest", "mocha", "unittest", "command"],
        },
        "working_dir": {
            "type": "string",
            "description": "Working directory for test execution (defaults to current directory)",
        },
    },
    "additionalProperties": False,
}

CHECK_REGRESSIONS_DESCRIPTION = """Check for test regressions against baseline.

Runs tests and compares results against a stored baseline to identify:
- Regressions: tests that previously passed but now fail
- New passes: tests that previously failed but now pass
- Unchanged: tests with the same status

Compatible with maker-reviewer Check 8 QA validation."""


def check_regressions_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle check_regressions tool invocation.

    Args:
        arguments: Tool arguments from MCP call
            - baseline: Optional path to baseline file
            - update_baseline: Whether to update baseline after check
            - framework: Optional framework override
            - working_dir: Optional working directory

    Returns:
        RegressionResult dict with:
            - regressions: List of tests that regressed
            - new_passes: List of tests that newly pass
            - unchanged: Count of tests with unchanged status
    """
    # Extract arguments
    baseline_path = arguments.get("baseline")
    update_baseline = arguments.get("update_baseline", False)
    framework = arguments.get("framework", "auto")
    working_dir = arguments.get("working_dir")

    # Validate working_dir using shared utility
    is_valid, validated_path, error_msg = validate_working_dir(working_dir)
    if not is_valid:
        return RegressionResult(
            regressions=[{
                "name": "validation_error",
                "previous_status": "UNKNOWN",
                "current_status": "ERROR",
                "message": error_msg,
            }],
            new_passes=[],
            unchanged=0,
            missing_tests=[],
        )
    working_dir = str(validated_path) if validated_path else None

    # Load config
    config = load_config(working_dir=working_dir, use_cache=False)

    # Override framework if specified
    if framework != "auto":
        config.test.framework = framework

    # Validate and determine baseline file path
    if baseline_path:
        effective_working_dir = Path(working_dir) if working_dir else Path.cwd()
        is_valid, validated_baseline, error_msg = validate_baseline_path(
            baseline_path, effective_working_dir
        )
        if not is_valid:
            return RegressionResult(
                regressions=[{
                    "name": "validation_error",
                    "previous_status": "UNKNOWN",
                    "current_status": "ERROR",
                    "message": error_msg,
                }],
                new_passes=[],
                unchanged=0,
                missing_tests=[],
            )
        baseline_file = validated_baseline if validated_baseline else Path(baseline_path)
    else:
        baseline_file = Path(working_dir or ".") / config.regression.baseline_file

    # Get appropriate adapter and run tests
    try:
        adapter = get_adapter(config, working_dir=working_dir)
        if adapter.name == "command":
            return {
                "status": "unavailable", "code": "COMMAND_REGRESSIONS_UNAVAILABLE",
                "message": "Project commands do not provide individual test results for baseline comparison.",
                "tests_executed": 0,
                **RegressionResult(regressions=[], new_passes=[], unchanged=0, new_tests=[], missing_tests=[]),
            }
        current_results = adapter.run_tests(config=config.test)
    except NoSupportedFramework as e:
        return {
            **e.to_result(),
            **RegressionResult(regressions=[], new_passes=[], unchanged=0, new_tests=[], missing_tests=[]),
        }
    except Exception as e:
        return RegressionResult(
            regressions=[{
                "name": "execution_error",
                "previous_status": "UNKNOWN",
                "current_status": "ERROR",
                "message": str(e),
            }],
            new_passes=[],
            unchanged=0,
            missing_tests=[],
        )

    # Warn if no tests were found in current results
    if current_results.get("total", 0) == 0:
        logger.warning("No tests found in current results - all comparisons will show as missing")
    
    # Load baseline if it exists
    baseline = _load_baseline(baseline_file)

    # Compare results
    result, flaky_counts = _compare_results(baseline, current_results, config.regression)

    # Update baseline if requested
    if update_baseline or (baseline is None and config.regression.auto_update_baseline):
        _save_baseline(baseline_file, current_results, flaky_counts)

    return dict(result)


def _load_baseline(baseline_file: Path) -> Optional[Dict[str, Any]]:
    """Load baseline test results from file.

    Args:
        baseline_file: Path to baseline JSON file

    Returns:
        Dict with 'tests' and 'flaky_counts', or None if no baseline
    """
    if not baseline_file.exists():
        return None

    try:
        with open(baseline_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate baseline structure
        if not isinstance(data, dict):
            logger.warning("Invalid baseline file %s: root element must be a dict", baseline_file)
            return None
        
        # Validate required fields
        tests_data = data.get("tests", {})
        flaky_counts_data = data.get("flaky_counts", {})
        
        if not isinstance(tests_data, dict):
            logger.warning("Invalid baseline file %s: 'tests' field must be a dict", baseline_file)
            return None
        
        if not isinstance(flaky_counts_data, dict):
            logger.warning("Invalid baseline file %s: 'flaky_counts' field must be a dict", baseline_file)
            return None
        
        # Validate test entries have valid status values
        # Support both old string format ("PASS") and new dict format ({"status": "PASS"})
        valid_statuses = {"PASS", "FAIL", "SKIP", "ERROR"}
        for test_name, test_data in list(tests_data.items()):
            if isinstance(test_data, str):
                # Old string format - convert to new dict format
                if test_data not in valid_statuses:
                    logger.warning("Invalid baseline file %s: test '%s' has invalid status '%s'",
                                 baseline_file, test_name, test_data)
                    return None
                tests_data[test_name] = {"status": test_data}  # Convert in place
            elif isinstance(test_data, dict):
                # New dict format - validate status
                status = test_data.get("status")
                if status not in valid_statuses:
                    logger.warning("Invalid baseline file %s: test '%s' has invalid status '%s'",
                                 baseline_file, test_name, status)
                    return None
            else:
                logger.warning("Invalid baseline file %s: test entry '%s' must be a string or dict",
                             baseline_file, test_name)
                return None
        
        # Validate flaky counts are integers
        for test_name, count in flaky_counts_data.items():
            if not isinstance(count, int) or count < 0:
                logger.warning("Invalid baseline file %s: flaky count for '%s' must be non-negative integer", 
                             baseline_file, test_name)
                return None
        
        return {
            "tests": tests_data,
            "flaky_counts": flaky_counts_data,
        }
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse baseline file %s: %s", baseline_file, e)
        return None
    except IOError as e:
        logger.warning("Failed to read baseline file %s: %s", baseline_file, e)
        return None


def _save_baseline(
    baseline_file: Path,
    test_results: Dict[str, Any],
    flaky_counts: Optional[Dict[str, int]] = None,
) -> bool:
    """Save current test results as baseline.

    Args:
        baseline_file: Path to save baseline JSON
        test_results: TestResult dict from adapter
        flaky_counts: Optional dict of test name to flaky count

    Returns:
        True if save succeeded, False otherwise
    """
    try:
        # Ensure directory exists
        baseline_file.parent.mkdir(parents=True, exist_ok=True)

        # Build baseline data
        tests = {}

        # Mark failures (using dict format for _load_baseline compatibility)
        for failure in test_results.get("failures", []):
            name = failure.get("name", "unknown")
            tests[name] = {"status": "FAIL"}

        # Mark passing tests (if available from adapter)
        passed_names = test_results.get("passed_names", [])
        for name in passed_names:
            tests[name] = {"status": "PASS"}

        baseline_data = {
            "tests": tests,
            "passed_tests": passed_names,  # Explicit list for backward compatibility
            "flaky_counts": flaky_counts or {},
            "summary": {
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "total": test_results.get("total", 0),
            },
        }

        # Use atomic write pattern to prevent corruption on crash
        # Write to temp file first, then atomically rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(baseline_file.parent),
            suffix=".tmp"
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(baseline_data, f, indent=2)
            # Atomic rename (os.replace is atomic on POSIX, near-atomic on Windows)
            os.replace(temp_path, baseline_file)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
        return True
    except (IOError, OSError, PermissionError) as e:
        logger.warning("Failed to save baseline file %s: %s", baseline_file, e)
        return False


def _compare_results(
    baseline: Optional[Dict[str, Any]],
    current: Dict[str, Any],
    config: RegressionConfig,
) -> tuple:
    """Compare current results against baseline.

    Args:
        baseline: Previous baseline dict with 'tests', 'passed_tests', and 'flaky_counts'
        current: Current TestResult dict
        config: Regression config with flaky settings

    Returns:
        Tuple of (RegressionResult, updated_flaky_counts)
    """
    regressions: list = []
    new_passes: list = []
    new_tests: list = []
    missing_tests: List[MissingTestItem] = []
    unchanged = 0

    # Extract baseline data
    baseline_tests = baseline.get("tests", {}) if baseline else {}
    baseline_passed_tests = baseline.get("passed_tests", []) if baseline else []
    flaky_counts = dict(baseline.get("flaky_counts", {})) if baseline else {}

    # Merge passed_tests into baseline_tests if not already present (backward compatibility)
    for name in baseline_passed_tests:
        if name not in baseline_tests:
            baseline_tests[name] = {"status": "PASS"}

    # Build current test status map
    current_tests: Dict[str, str] = {}
    for failure in current.get("failures", []):
        name = failure.get("name", "unknown")
        current_tests[name] = "FAIL"

    # Add current passed tests (if available from adapter)
    for name in current.get("passed_names", []):
        if name not in current_tests:  # Don't override failures
            current_tests[name] = "PASS"

    # If no baseline, all tests are "new"
    if baseline is None:
        for test_name, status in current_tests.items():
            new_tests.append(NewTestItem(
                name=test_name,
                current_status=status,
            ))
        return (
            RegressionResult(
                regressions=[],
                new_passes=[],
                unchanged=0,
                new_tests=new_tests,
                missing_tests=[],
            ),
            flaky_counts,
        )

    # Compare against baseline
    for test_name, test_data in baseline_tests.items():
        # Extract status from dict format, with backward compat for old string format
        previous_status = test_data.get("status") if isinstance(test_data, dict) else test_data
        current_status = current_tests.get(test_name)
        if current_status is None:
            # Test from baseline not found in current results
            # This could mean the test was removed or not run - treat as MISSING
            logger.warning(
                "Baseline test '%s' not found in current results - may have been removed or skipped",
                test_name
            )
            current_status = "MISSING"

        if current_status == "MISSING":
            # Test is missing from current results - add to missing_tests
            missing_tests.append(MissingTestItem(
                name=test_name,
                previous_status=previous_status,
                message="Test not found in current results (possibly removed or skipped)"
            ))
        elif previous_status == "PASS" and current_status == "FAIL":
            # Increment flaky count for status flip
            flaky_counts[test_name] = flaky_counts.get(test_name, 0) + 1

            # Skip if flaky and ignore_flaky is True
            if config.ignore_flaky and flaky_counts[test_name] >= config.flaky_threshold:
                unchanged += 1
                continue

            # Regression: was passing, now failing
            failure_msg = None
            for f in current.get("failures", []):
                if f.get("name") == test_name:
                    failure_msg = f.get("message")
                    break

            regressions.append(RegressionItem(
                name=test_name,
                previous_status="PASS",
                current_status="FAIL",
                message=failure_msg,
            ))

        elif previous_status == "FAIL" and current_status == "PASS":
            # Track flip for flaky detection
            flaky_counts[test_name] = flaky_counts.get(test_name, 0) + 1

            # Improvement: was failing, now passing
            new_passes.append(NewPassItem(
                name=test_name,
                previous_status="FAIL",
                current_status="PASS",
            ))

        else:
            # Unchanged - decay flaky count for stable tests
            if test_name in flaky_counts and flaky_counts[test_name] > 0:
                flaky_counts[test_name] = max(0, flaky_counts[test_name] - 1)
                if flaky_counts[test_name] == 0:
                    logger.debug(f"Flaky count for '{test_name}' decayed to 0 due to stable behavior")
            unchanged += 1

    # Check for new tests not in baseline (both passing and failing)
    for test_name, status in current_tests.items():
        if test_name not in baseline_tests:
            new_tests.append(NewTestItem(
                name=test_name,
                current_status=status,
            ))

    return (
        RegressionResult(
            regressions=regressions,
            new_passes=new_passes,
            unchanged=unchanged,
            new_tests=new_tests,
            missing_tests=missing_tests,
        ),
        flaky_counts,
    )
