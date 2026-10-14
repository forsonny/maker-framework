"""
get_coverage tool implementation for QA MCP Server.

Collects code coverage metrics using the appropriate test framework
adapter and returns structured results compatible with maker-reviewer.
"""

from typing import Dict, Any
from pathlib import Path

from ..types import CoverageResult
from ..config import QAConfig, load_config
from ..adapter_factory import get_adapter, NoSupportedFramework
from ..utils import validate_working_dir


# MCP Tool Schema for get_coverage
GET_COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "threshold": {
            "type": "number",
            "description": "Minimum coverage percentage to pass (default: 70)",
            "minimum": 0,
            "maximum": 100,
        },
        "framework": {
            "type": "string",
            "description": "Test framework to use for coverage (pytest, jest, mocha, unittest, or 'auto')",
            "enum": ["auto", "pytest", "jest", "mocha", "unittest", "command"],
        },
        "working_dir": {
            "type": "string",
            "description": "Working directory for coverage collection (defaults to current directory)",
        },
        "verbose": {
            "type": "boolean",
            "description": "Enable verbose output for debugging (default: false)",
        },
    },
    "additionalProperties": False,
}

GET_COVERAGE_DESCRIPTION = """Get code coverage metrics.

Runs tests with coverage instrumentation and returns coverage percentage,
uncovered lines, and whether the coverage meets the threshold.

Note: The meets_threshold field is informational - this tool does not
fail on low coverage. Enforcement is handled by maker-reviewer.

Compatible with maker-reviewer Check 8 QA validation."""


def get_coverage_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_coverage tool invocation.

    Args:
        arguments: Tool arguments from MCP call
            - threshold: Optional coverage threshold percentage
            - framework: Optional framework override
            - working_dir: Optional working directory
            - verbose: Optional verbose output flag

    Returns:
        CoverageResult dict with:
            - percentage: Coverage percentage (0-100)
            - uncovered_lines: List of uncovered line details
            - meets_threshold: Whether coverage meets threshold
    """
    # Extract arguments
    threshold = arguments.get("threshold")
    framework = arguments.get("framework", "auto")
    working_dir = arguments.get("working_dir")
    verbose = arguments.get("verbose", False)

    # Validate working_dir using shared utility
    is_valid, validated_path, error_msg = validate_working_dir(working_dir)
    if not is_valid:
        return CoverageResult(
            percentage=0.0,
            uncovered_lines=[{
                "file": "validation_error",
                "line": 0,
                "content": error_msg,
            }],
            meets_threshold=False,
        )
    working_dir = str(validated_path) if validated_path else None

    # Load config
    config = load_config(working_dir=working_dir, use_cache=False)

    # Override framework if specified (with validation)
    if framework != "auto":
        allowed_frameworks = ["pytest", "jest", "mocha", "unittest", "command"]
        if framework not in allowed_frameworks:
            return CoverageResult(
                percentage=0.0,
                uncovered_lines=[{
                    "file": "validation_error",
                    "line": 0,
                    "content": f"Invalid framework '{framework}'. Must be one of: {allowed_frameworks}",
                }],
                meets_threshold=False,
            )
        config.test.framework = framework

    # Override threshold if specified with validation
    if threshold is not None:
        try:
            threshold_val = float(threshold)
            if threshold_val < 0 or threshold_val > 100:
                return CoverageResult(
                    percentage=0.0,
                    uncovered_lines=[{
                        "file": "validation_error",
                        "line": 0,
                        "content": f"Threshold must be between 0 and 100, got {threshold_val}",
                    }],
                    meets_threshold=False,
                )
            config.coverage.threshold = threshold_val
        except (TypeError, ValueError) as e:
            return CoverageResult(
                percentage=0.0,
                uncovered_lines=[{
                    "file": "validation_error",
                    "line": 0,
                    "content": f"Invalid threshold value: {e}",
                }],
                meets_threshold=False,
            )

    # Store verbose flag in config for potential adapter use (with safety check)
    if hasattr(config, 'verbose'):
        config.verbose = verbose
    else:
        # Handle malformed config that might not have verbose attribute
        setattr(config, 'verbose', verbose)

    # Get appropriate adapter
    try:
        adapter = get_adapter(config, working_dir=working_dir)
    except NoSupportedFramework as e:
        return {
            **e.to_result(),
            **CoverageResult(percentage=None, uncovered_lines=[], meets_threshold=False),
        }
    except ValueError as e:
        return CoverageResult(
            percentage=0.0,
            uncovered_lines=[{
                "file": "error",
                "line": 0,
                "content": str(e),
            }],
            meets_threshold=False,
        )

    # Check if adapter supports coverage
    if adapter.name == "command":
        return adapter.get_coverage(config=config.coverage, verbose=verbose)
    if not adapter.supports_coverage():
        return CoverageResult(
            percentage=0.0,
            uncovered_lines=[{
                "file": "error",
                "line": 0,
                "content": f"Adapter {adapter.name} does not support coverage",
            }],
            meets_threshold=False,
        )

    # Get coverage
    try:
        result = adapter.get_coverage(config=config.coverage, verbose=verbose)

        # Ensure result is a proper dict
        return dict(result)

    except Exception as e:
        return CoverageResult(
            percentage=0.0,
            uncovered_lines=[{
                "file": "error",
                "line": 0,
                "content": f"Error collecting coverage: {e}",
            }],
            meets_threshold=False,
        )
