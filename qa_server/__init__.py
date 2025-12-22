"""
QA MCP Server for MAKER Framework

A Model Context Protocol (MCP) server providing QA tools for automated testing,
coverage analysis, and regression detection. Designed specifically for integration
with the MAKER framework's maker-reviewer agent.

Tools provided:
- run_tests: Execute test suites across multiple frameworks
- get_coverage: Retrieve code coverage metrics
- check_regressions: Compare test results against baselines
- generate_tests: Generate test stubs for source files

Supported test frameworks:
- Python: pytest, unittest
- JavaScript: Jest, Mocha
"""

__version__ = "1.0.0"
__author__ = "MAKER Framework"

# Public API exports
from .server import MCPServer, CancellationToken, CancellationError
from .config import (
    QAConfig,
    TestConfig,
    CoverageConfig,
    RegressionConfig,
    load_config,
    sanitize_extra_args,
    sanitize_hooks,
)
from .adapter_factory import get_adapter, detect_all_frameworks
from .types import (
    TestResult,
    CoverageResult,
    RegressionResult,
    GenerateTestsResult,
    GeneratedTestFile,
    NewTestItem,
)
from .constants import (
    MAX_UNCOVERED_LINES_PER_FILE,
    MAX_UNCOVERED_LINES_TOTAL,
    DEFAULT_MAX_FILES,
    TOOL_TIMEOUT_SECONDS,
    DEFAULT_COVERAGE_THRESHOLD,
)

__all__ = [
    # Server
    "MCPServer",
    "CancellationToken",
    "CancellationError",
    # Configuration
    "QAConfig",
    "TestConfig",
    "CoverageConfig",
    "RegressionConfig",
    "load_config",
    "sanitize_extra_args",
    "sanitize_hooks",
    # Adapters
    "get_adapter",
    "detect_all_frameworks",
    # Types
    "TestResult",
    "CoverageResult",
    "RegressionResult",
    "GenerateTestsResult",
    "GeneratedTestFile",
    "NewTestItem",
    # Constants
    "MAX_UNCOVERED_LINES_PER_FILE",
    "MAX_UNCOVERED_LINES_TOTAL",
    "DEFAULT_MAX_FILES",
    "TOOL_TIMEOUT_SECONDS",
    "DEFAULT_COVERAGE_THRESHOLD",
]
