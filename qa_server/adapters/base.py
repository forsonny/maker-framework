"""
Base adapter interface for test framework integration.

All test framework adapters must implement this interface to provide
consistent access to test execution and coverage collection.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, List
from pathlib import Path

from ..types import TestResult, CoverageResult
from ..config import TestConfig, CoverageConfig
from ..constants import HOOK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Abstract base class for test framework adapters.

    Each adapter provides:
    - Test detection (detect if framework is used in project)
    - Test execution with result collection
    - Coverage collection (if supported)
    """

    # Framework identifier
    name: str = "base"

    # File patterns for framework detection
    detection_patterns: List[str] = []

    def __init__(self, working_dir: Optional[str] = None):
        """Initialize adapter.

        Args:
            working_dir: Working directory for test execution.
                        Defaults to current directory.
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()

    @abstractmethod
    def detect(self) -> bool:
        """Detect if this test framework is used in the project.

        Returns:
            True if framework is detected, False otherwise
        """
        pass

    @abstractmethod
    def run_tests(
        self,
        pattern: Optional[str] = None,
        config: Optional[TestConfig] = None,
        verbose: bool = False,
    ) -> TestResult:
        """Execute tests and return results.

        Args:
            pattern: Optional glob pattern to filter tests
            config: Test configuration options

        Returns:
            TestResult with pass/fail counts and failure details
        """
        pass

    @abstractmethod
    def get_coverage(
        self,
        config: Optional[CoverageConfig] = None,
        verbose: bool = False,
    ) -> CoverageResult:
        """Collect coverage metrics.

        Args:
            config: Coverage configuration options
            verbose: Enable verbose output for debugging

        Returns:
            CoverageResult with coverage percentage and uncovered lines
        """
        pass

    def supports_coverage(self) -> bool:
        """Check if this adapter supports coverage collection.

        Returns:
            True if coverage is supported
        """
        return True

    def get_default_patterns(self) -> List[str]:
        """Get default test file patterns for this framework.

        Returns:
            List of glob patterns for test discovery
        """
        return []

    def _create_empty_test_result(self, error: str) -> TestResult:
        """Create an empty test result with error.

        Args:
            error: Error message to include

        Returns:
            TestResult with zero counts and error in failures
        """
        return TestResult(
            passed=0,
            failed=0,
            total=0,
            failures=[{
                "name": "adapter_error",
                "message": error,
                "file": None,
                "line": None,
            }],
            duration_ms=0,
            passed_names=[],
        )

    def _create_empty_coverage_result(
        self,
        error: str,
        threshold: float = 70.0,
    ) -> CoverageResult:
        """Create an empty coverage result with error.

        Args:
            error: Error message (stored in uncovered_lines)
            threshold: Coverage threshold

        Returns:
            CoverageResult with 0% coverage
        """
        return CoverageResult(
            percentage=0.0,
            uncovered_lines=[{
                "file": "error",
                "line": 0,
                "content": error,
            }],
            meets_threshold=False,
        )

    def _run_hooks(
        self,
        hooks: List[str],
        phase: str,
        timeout: int = HOOK_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """Execute a list of shell commands as hooks.

        Args:
            hooks: List of shell commands to execute
            phase: Phase name for logging (e.g., "pre", "post")
            timeout: Timeout in seconds for each hook command

        Returns:
            None if all hooks succeeded, error message if any failed
        """
        if not hooks:
            return None

        for i, hook in enumerate(hooks):
            logger.info(f"Running {phase}-hook {i + 1}/{len(hooks)}: {hook}")
            try:
                result = subprocess.run(
                    hook,
                    shell=True,
                    cwd=str(self.working_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or f"Exit code {result.returncode}"
                    logger.error(f"{phase}-hook failed: {error_msg}")
                    return f"{phase}-hook '{hook}' failed: {error_msg}"
            except subprocess.TimeoutExpired:
                logger.error(f"{phase}-hook timed out after {timeout}s: {hook}")
                return f"{phase}-hook '{hook}' timed out after {timeout} seconds"
            except Exception as e:
                logger.error(f"{phase}-hook error: {e}")
                return f"{phase}-hook '{hook}' error: {e}"

        logger.info(f"All {phase}-hooks completed successfully")
        return None
