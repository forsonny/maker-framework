"""
Python unittest adapter for QA MCP Server.

Provides test execution and coverage collection using Python's
built-in unittest framework and coverage.py.
"""

import logging
import re
import subprocess
import json
import time
import sys
from typing import Optional, List
from pathlib import Path

from .base import BaseAdapter

logger = logging.getLogger(__name__)
from ..types import TestResult, CoverageResult, TestFailure, UncoveredLine
from ..config import TestConfig, CoverageConfig
from ..constants import MAX_UNCOVERED_LINES_PER_FILE, MAX_UNCOVERED_LINES_TOTAL


class UnittestAdapter(BaseAdapter):
    """Adapter for Python unittest framework.

    Detection:
    - test*.py files with unittest imports
    - Tests using TestCase subclasses
    - No pytest/conftest.py present (fall back to unittest)

    Test execution:
    - Uses python -m unittest discover with custom output parsing
    - Can also use pytest as runner for better output

    Coverage:
    - Uses coverage.py for coverage collection
    """

    name = "unittest"
    detection_patterns = [
        "test*.py",
        "**/test*.py",
    ]

    def get_default_patterns(self) -> List[str]:
        """Get default test file patterns for unittest."""
        return ["test*.py", "**/test*.py"]

    def detect(self) -> bool:
        """Detect if unittest is used in the project.

        Note: Returns True as fallback for Python projects without pytest.
        """
        # Check for test files with unittest imports
        test_files = list(self.working_dir.glob("test*.py")) + \
                     list(self.working_dir.glob("**/test*.py"))

        for test_file in test_files[:10]:  # Check first 10 files
            try:
                content = test_file.read_text()
                if "import unittest" in content or "from unittest" in content:
                    return True
                if "TestCase" in content:
                    return True
            except (IOError, UnicodeDecodeError) as e:
                logger.debug(f"Error reading test file {test_file}: {e}")
                continue

        # As fallback, check if there are any Python test files and no pytest
        if test_files:
            conftest = self.working_dir / "conftest.py"
            if not conftest.exists():
                return True

        return False

    def run_tests(
        self,
        pattern: Optional[str] = None,
        config: Optional[TestConfig] = None,
        verbose: bool = False,
    ) -> TestResult:
        """Execute tests using unittest."""
        config = config or TestConfig()
        start_time = time.time()

        # Run pre-test hooks if configured
        if config.pre_hooks:
            hook_error = self._run_hooks(config.pre_hooks, "pre")
            if hook_error:
                return self._create_empty_test_result(hook_error)

        # Determine effective patterns (priority: explicit pattern > config.patterns > default)
        effective_patterns: Optional[List[str]] = None
        if pattern:
            effective_patterns = [pattern]
        elif config.patterns:
            effective_patterns = config.patterns
        else:
            effective_patterns = self.get_default_patterns()

        # Try using unittest discover first (expected for unittest adapter)
        unittest_result = self._run_unittest_discover(effective_patterns, config, start_time, verbose)
        if unittest_result is not None and unittest_result["total"] > 0:
            # Run post-test hooks if configured
            if config.post_hooks:
                hook_error = self._run_hooks(config.post_hooks, "post")
                if hook_error:
                    logger.warning(f"Post-hook error (tests still reported): {hook_error}")
            return unittest_result

        # Fall back to pytest as runner if unittest produced no results
        pytest_result = self._try_pytest_runner(effective_patterns, config, start_time, verbose)
        if pytest_result is not None:
            # Run post-test hooks if configured
            if config.post_hooks:
                hook_error = self._run_hooks(config.post_hooks, "post")
                if hook_error:
                    logger.warning(f"Post-hook error (tests still reported): {hook_error}")
            return pytest_result

        # Run post-test hooks even on failure
        if config.post_hooks:
            hook_error = self._run_hooks(config.post_hooks, "post")
            if hook_error:
                logger.warning(f"Post-hook error (tests still reported): {hook_error}")

        # Return unittest result if pytest also failed, with fallback for None
        if unittest_result is None:
            return self._create_empty_test_result("No test results available from unittest or pytest")
        return unittest_result

    def _try_pytest_runner(
        self,
        patterns: Optional[List[str]],
        config: TestConfig,
        start_time: float,
        verbose: bool = False,
    ) -> Optional[TestResult]:
        """Try running tests with pytest as the runner."""
        try:
            verbosity_flag = "-vv" if verbose else "-v"
            cmd = [sys.executable, "-m", "pytest", verbosity_flag, "--tb=short"]
            if patterns:
                cmd.extend(patterns)

            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=config.timeout_seconds,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            return self._parse_pytest_output(result.stdout, result.returncode, duration_ms)

        except FileNotFoundError:
            return None  # pytest not available, use unittest
        except subprocess.TimeoutExpired:
            # pytest timed out, fall back to unittest discover
            return None

    def _run_unittest_discover(
        self,
        patterns: Optional[List[str]],
        config: TestConfig,
        start_time: float,
        verbose: bool = False,
    ) -> TestResult:
        """Run tests using unittest discover."""
        # Verbose output supplies stable test names for regression baselines.
        cmd = [sys.executable, "-m", "unittest", "discover", "-v"]

        # NOTE: Python's unittest discover only supports a single -p pattern.
        # When multiple patterns are provided (e.g., ["test*.py", "*_test.py"]),
        # only the first pattern is used. This is a limitation of the unittest
        # module's discover command. For projects requiring multiple test file
        # patterns, consider using pytest instead, which supports multiple
        # patterns via glob matching and the --ignore option.
        if patterns:
            first_pattern = patterns[0].replace("\\", "/")
            directory, _, filename = first_pattern.rpartition("/")
            if directory and not any(char in directory for char in "*?["):
                cmd.extend(["-s", directory])
            cmd.extend(["-p", filename or first_pattern])
        cmd.extend(config.extra_args)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=config.timeout_seconds,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            return self._parse_unittest_output(
                result.stdout + result.stderr,
                result.returncode,
                duration_ms,
            )

        except subprocess.TimeoutExpired:
            return self._create_empty_test_result(
                f"Test execution timed out after {config.timeout_seconds} seconds"
            )
        except Exception as e:
            return self._create_empty_test_result(f"Error running unittest: {e}")

    def _parse_pytest_output(
        self,
        output: str,
        returncode: int,
        duration_ms: int,
    ) -> TestResult:
        """Parse pytest text output."""

        passed = 0
        failed = 0
        failures: List[TestFailure] = []

        for line in output.split("\n"):
            line = line.strip()
            if "passed" in line or "failed" in line:
                passed_match = re.search(r"(\d+) passed", line)
                failed_match = re.search(r"(\d+) failed", line)
                if passed_match:
                    passed = int(passed_match.group(1))
                if failed_match:
                    failed = int(failed_match.group(1))

            if line.startswith("FAILED"):
                test_name = line.replace("FAILED", "").strip()
                failures.append(TestFailure(
                    name=test_name,
                    message="Test failed",
                    file=None,
                    line=None,
                ))

        total = passed + failed

        if total == 0 and returncode != 0:
            # Exit code 5 = no tests collected (not a failure, just informational)
            if returncode == 5:
                failures.append(TestFailure(
                    name="pytest_info",
                    message="No tests collected (pytest exit code 5)",
                    file=None,
                    line=None,
                ))
            else:
                failures.append(TestFailure(
                    name="pytest_error",
                    message=f"pytest exited with code {returncode}",
                    file=None,
                    line=None,
                ))
                failed = 1
                total = 1

        # Note: pytest text output parsing cannot extract individual passed test names.
        # passed_names will be empty - for full regression tracking, use pytest with json-report.
        return TestResult(
            passed=passed,
            failed=failed,
            total=total,
            failures=failures,
            duration_ms=duration_ms,
            passed_names=[],
        )

    def _parse_unittest_output(
        self,
        output: str,
        returncode: int,
        duration_ms: int,
    ) -> TestResult:
        """Parse unittest verbose output."""

        passed = 0
        failed = 0
        failures: List[TestFailure] = []
        passed_names: List[str] = []

        lines = output.split("\n")
        skipped = sum(" ... skipped" in line.lower() for line in lines)
        for line in lines:
            # Count OK/FAIL results and extract test names
            if " ... ok" in line.lower():
                passed += 1
                # Extract test name for passed tests
                test_name = line.split(" ... ")[0].strip() if " ... " in line else None
                if test_name:
                    passed_names.append(test_name)
            elif " ... fail" in line.lower() or " ... error" in line.lower():
                failed += 1
                # Extract test name
                test_name = line.split(" ... ")[0].strip() if " ... " in line else "unknown"
                failures.append(TestFailure(
                    name=test_name,
                    message="Test failed (see output for details)",
                    file=None,
                    line=None,
                ))

        # Also check for summary line "Ran X tests"
        for line in lines:
            match = re.search(r"Ran (\d+) tests?", line)
            if match:
                total_from_summary = int(match.group(1))
                if passed + failed == 0:
                    # No individual results parsed, use summary
                    if returncode == 0:
                        passed = max(0, total_from_summary - skipped)
                    else:
                        # Some failed but we don't know how many
                        failed = 1
                        passed = max(0, total_from_summary - 1)

        total = passed + failed

        return TestResult(
            passed=passed,
            failed=failed,
            total=total,
            failures=failures,
            duration_ms=duration_ms,
            passed_names=passed_names,
        )

    def _build_coverage_args(
        self,
        source_patterns: List[str],
        exclude_patterns: List[str],
    ) -> List[str]:
        """Build coverage.py --source and --omit arguments from patterns.

        Extracts base directories from source glob patterns for coverage.py's
        --source flag, and formats exclude patterns for --omit flag.

        Args:
            source_patterns: Glob patterns like ["src/**/*.py", "lib/**/*.py"]
            exclude_patterns: Glob patterns like ["**/test/**", "**/__pycache__/**"]

        Returns:
            List of coverage.py arguments like ["--source=src", "--omit=**/test/**"]
        """
        args = []

        # Extract base directories from source patterns
        sources = set()
        for pattern in source_patterns:
            # Extract base directory before any glob wildcards
            parts = pattern.replace("\\", "/").split("/")
            base_parts = []
            for part in parts:
                if "*" in part or "?" in part or "[" in part:
                    break
                base_parts.append(part)
            if base_parts:
                base_dir = "/".join(base_parts)
                # Verify directory exists
                if (self.working_dir / base_dir).exists():
                    sources.add(base_dir)

        for src in sorted(sources):
            args.append(f"--source={src}")

        # Add exclude patterns as comma-separated --omit
        if exclude_patterns:
            args.append(f"--omit={','.join(exclude_patterns)}")

        return args

    def get_coverage(
        self,
        config: Optional[CoverageConfig] = None,
        verbose: bool = False,
    ) -> CoverageResult:
        """Collect coverage using coverage.py."""
        config = config or CoverageConfig()

        coverage_json = self.working_dir / ".coverage.json"
        cmd = [
            sys.executable, "-m", "coverage", "run",
        ]

        if verbose:
            logger.info("Running coverage with verbose output")

        # Add source and exclude patterns if configured
        if config.source_patterns or config.exclude_patterns:
            cmd.extend(self._build_coverage_args(
                config.source_patterns,
                config.exclude_patterns,
            ))

        # Add unittest discover command
        cmd.extend(["-m", "unittest", "discover"])

        try:
            subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                timeout=config.timeout_seconds,
            )

            subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", str(coverage_json)],
                cwd=str(self.working_dir),
                capture_output=True,
            )

            if coverage_json.exists():
                return self._parse_coverage_json(coverage_json, config.threshold)

            result = subprocess.run(
                [sys.executable, "-m", "coverage", "report"],
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            return self._parse_coverage_text(result.stdout, config.threshold)

        except subprocess.TimeoutExpired:
            return self._create_empty_coverage_result(
                f"Coverage collection timed out after {config.timeout_seconds} seconds",
                config.threshold,
            )
        except FileNotFoundError:
            return self._create_empty_coverage_result(
                "coverage not found. Install with: pip install coverage",
                config.threshold,
            )
        except Exception as e:
            return self._create_empty_coverage_result(str(e), config.threshold)
        finally:
            self._cleanup_temp_files(coverage_json)

    def _parse_coverage_json(
        self,
        report_path: Path,
        threshold: float,
    ) -> CoverageResult:
        """Parse coverage JSON report."""
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)

            totals = report.get("totals", {})
            percentage = totals.get("percent_covered", 0.0)

            uncovered: List[UncoveredLine] = []
            for file_path, file_data in report.get("files", {}).items():
                if len(uncovered) >= MAX_UNCOVERED_LINES_TOTAL:
                    break  # Enforce total limit
                missing_lines = file_data.get("missing_lines", [])
                remaining = MAX_UNCOVERED_LINES_TOTAL - len(uncovered)
                per_file_limit = min(MAX_UNCOVERED_LINES_PER_FILE, remaining)
                for line_num in missing_lines[:per_file_limit]:
                    uncovered.append(UncoveredLine(
                        file=file_path,
                        line=line_num,
                        content=None,
                    ))

            return CoverageResult(
                percentage=round(percentage, 2),
                uncovered_lines=uncovered,
                meets_threshold=percentage >= threshold,
            )

        except json.JSONDecodeError as e:
            return self._create_empty_coverage_result(f"Invalid JSON in coverage report: {e}", threshold)
        except Exception as e:
            return self._create_empty_coverage_result(str(e), threshold)

    def _parse_coverage_text(self, output: str, threshold: float) -> CoverageResult:
        """Parse coverage text report."""

        percentage = 0.0
        for line in output.split("\n"):
            if line.strip().startswith("TOTAL"):
                match = re.search(r"(\d+)%", line)
                if match:
                    percentage = float(match.group(1))
                break

        return CoverageResult(
            percentage=percentage,
            uncovered_lines=[],
            meets_threshold=percentage >= threshold,
        )

    def _cleanup_temp_files(self, primary_file: Path) -> None:
        """Clean up temporary files created during coverage collection.

        Args:
            primary_file: Primary temp file path (e.g., coverage JSON report)
        """
        temp_files = [
            primary_file,
            self.working_dir / ".coverage",
            self.working_dir / ".coverage.json",
        ]
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except (IOError, OSError) as e:
                logger.info(f"Cleanup error (ignored): {e}")
