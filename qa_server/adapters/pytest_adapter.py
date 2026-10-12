"""
Pytest adapter for QA MCP Server.

Provides test execution and coverage collection using pytest
and coverage.py.
"""

import logging
import re
import subprocess
import sys
import json
import time
from typing import Optional, List
from pathlib import Path

from .base import BaseAdapter

logger = logging.getLogger(__name__)
from ..types import TestResult, CoverageResult, TestFailure, UncoveredLine
from ..config import TestConfig, CoverageConfig
from ..constants import MAX_UNCOVERED_LINES_PER_FILE, MAX_UNCOVERED_LINES_TOTAL


class PytestAdapter(BaseAdapter):
    """Adapter for pytest test framework.

    Detection:
    - conftest.py exists
    - pytest in requirements.txt or pyproject.toml
    - test_*.py or *_test.py files exist

    Test execution:
    - Uses pytest with --json-report plugin if available
    - Falls back to parsing pytest output

    Coverage:
    - Uses coverage.py via pytest-cov or standalone coverage run
    """

    name = "pytest"
    detection_patterns = [
        "conftest.py",
        "**/conftest.py",
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
    ]

    def __init__(self, working_dir: Optional[str] = None):
        super().__init__(working_dir)
        self._json_report_available: Optional[bool] = None

    def get_default_patterns(self) -> List[str]:
        """Get default test file patterns for pytest."""
        return ["test_*.py", "*_test.py", "**/test_*.py", "**/*_test.py"]

    def detect(self) -> bool:
        """Detect if pytest is used in the project."""
        # Check for pytest config files
        for pattern in self.detection_patterns:
            if list(self.working_dir.glob(pattern)):
                # For pyproject.toml, check if it mentions pytest
                if pattern == "pyproject.toml":
                    pyproject = self.working_dir / "pyproject.toml"
                    if pyproject.exists():
                        try:
                            content = pyproject.read_text(encoding="utf-8")
                            if "pytest" in content.lower():
                                return True
                        except (IOError, UnicodeDecodeError) as e:
                            logger.debug(f"Error reading pyproject.toml: {e}")
                        continue
                return True

        # Check for test files
        test_patterns = ["test_*.py", "*_test.py", "**/test_*.py", "**/*_test.py"]
        for pattern in test_patterns:
            if list(self.working_dir.glob(pattern)):
                return True

        # Check requirements.txt
        requirements = self.working_dir / "requirements.txt"
        if requirements.exists():
            try:
                req_content = requirements.read_text(encoding="utf-8").lower()
                if "pytest" in req_content:
                    return True
            except (IOError, UnicodeDecodeError) as e:
                logger.debug(f"Error reading requirements.txt: {e}")

        return False

    def _has_json_report_plugin(self) -> bool:
        """Check if pytest-json-report plugin is installed (cached)."""
        if self._json_report_available is not None:
            return self._json_report_available

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--help"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
            )
            self._json_report_available = "--json-report" in result.stdout
        except Exception as e:
            logger.debug(f"Error checking json-report plugin: {e}")
            self._json_report_available = False

        return self._json_report_available

    def run_tests(
        self,
        pattern: Optional[str] = None,
        config: Optional[TestConfig] = None,
        verbose: bool = False,
    ) -> TestResult:
        """Execute tests using pytest."""
        config = config or TestConfig()
        start_time = time.time()

        # Run pre-test hooks if configured
        if config.pre_hooks:
            hook_error = self._run_hooks(config.pre_hooks, "pre")
            if hook_error:
                return self._create_empty_test_result(hook_error)

        # Build pytest command with verbosity based on parameter
        verbosity_flag = "-vv" if verbose else "-v"
        cmd = [sys.executable, "-m", "pytest", verbosity_flag, "--tb=short"]

        # Add parallel execution if configured (requires pytest-xdist)
        if config.parallel:
            cmd.extend(["-n", "auto"])

        # Only add JSON report if plugin is available
        json_report_path = self.working_dir / ".pytest_report.json"
        use_json_report = self._has_json_report_plugin()
        if use_json_report:
            cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])

        # Add pattern filter
        patterns = [pattern] if pattern else config.patterns
        if patterns:
            paths = []
            for item in patterns:
                if any(char in item for char in "*?["):
                    paths.extend(str(p) for p in self.working_dir.glob(item) if p.is_file())
                else:
                    paths.append(item)
            if not paths:
                return self._create_empty_test_result("No tests matched the requested patterns")
            cmd.extend(dict.fromkeys(paths))

        # Add extra args from config
        cmd.extend(config.extra_args)

        # Add timeout
        timeout = config.timeout_seconds

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Try to parse JSON report if we used it
            try:
                if use_json_report and json_report_path.exists():
                    test_result = self._parse_json_report(json_report_path, duration_ms)
                else:
                    # Fall back to parsing stdout
                    test_result = self._parse_pytest_output(result.stdout, result.returncode, duration_ms)

                # Run post-test hooks if configured (regardless of test outcome)
                if config.post_hooks:
                    hook_error = self._run_hooks(config.post_hooks, "post")
                    if hook_error:
                        logger.warning(f"Post-hook error (tests still reported): {hook_error}")

                return test_result
            finally:
                # Clean up temp files
                self._cleanup_temp_files(json_report_path)

        except subprocess.TimeoutExpired:
            # Still run post-hooks on timeout
            if config.post_hooks:
                self._run_hooks(config.post_hooks, "post")
            return self._create_empty_test_result(
                f"Test execution timed out after {timeout} seconds"
            )
        except FileNotFoundError:
            return self._create_empty_test_result(
                "pytest not found. Install with: pip install pytest"
            )
        except Exception as e:
            # Still run post-hooks on error
            if config.post_hooks:
                self._run_hooks(config.post_hooks, "post")
            return self._create_empty_test_result(f"Error running pytest: {e}")

    def _parse_json_report(self, report_path: Path, duration_ms: int) -> TestResult:
        """Parse pytest JSON report."""
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)

            summary = report.get("summary", {})
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            total = summary.get("total", passed + failed)

            failures: List[TestFailure] = []
            passed_names: List[str] = []

            for test in report.get("tests", []):
                outcome = test.get("outcome")
                nodeid = test.get("nodeid", "unknown")

                if outcome == "failed":
                    call = test.get("call", {})
                    failures.append(TestFailure(
                        name=nodeid,
                        message=call.get("longrepr", "Test failed"),
                        file=nodeid.split("::")[0] if "::" in nodeid else None,
                        line=call.get("lineno"),
                    ))
                elif outcome == "passed":
                    passed_names.append(nodeid)

            return TestResult(
                passed=passed,
                failed=failed,
                total=total,
                failures=failures,
                duration_ms=duration_ms,
                passed_names=passed_names,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in pytest report: {e}")
            return self._create_empty_test_result(f"Invalid JSON in report: {e}")
        except Exception as e:
            logger.exception("Error parsing JSON report")
            return self._create_empty_test_result(f"Error parsing JSON report: {e}")

    def _parse_pytest_output(
        self,
        output: str,
        returncode: int,
        duration_ms: int,
    ) -> TestResult:
        """Parse pytest text output when JSON report unavailable."""
        passed = 0
        failed = 0
        failures: List[TestFailure] = []

        # First pass: extract error messages from short traceback sections
        # Pytest --tb=short format shows errors with "E " prefix lines
        error_messages: dict[str, tuple[str, Optional[str], Optional[int]]] = {}
        lines = output.split("\n")
        current_test: Optional[str] = None
        current_file: Optional[str] = None
        current_line: Optional[int] = None

        for line in lines:
            # Detect test function header (e.g., "test_file.py::test_function FAILED")
            if "FAILED" in line and "::" in line:
                # Extract test name from lines like "test_file.py::test_func FAILED"
                parts = line.replace("FAILED", "").strip()
                if parts:
                    current_test = parts
                    if "::" in current_test:
                        current_file = current_test.split("::")[0]
            elif line.strip().startswith("_") and line.strip().endswith("_") and " " in line:
                # Section header like "_ test_function _" - extract test name
                test_match = re.search(r"_+\s+(.+?)\s+_+", line)
                if test_match:
                    current_test = test_match.group(1).strip()

            # Look for file:line references in traceback
            file_line_match = re.match(r"^(\S+\.py):(\d+):", line)
            if file_line_match and current_test:
                current_file = file_line_match.group(1)
                current_line = int(file_line_match.group(2))

            # Capture error lines (pytest prefixes assertion details with "E ")
            if line.startswith("E ") and current_test:
                error_content = line[2:].strip()
                if current_test not in error_messages:
                    error_messages[current_test] = (error_content, current_file, current_line)
                else:
                    existing_msg, existing_file, existing_line = error_messages[current_test]
                    # Prefer assertion or error messages over generic ones
                    if "assert" in error_content.lower() or "Error" in error_content:
                        error_messages[current_test] = (
                            error_content,
                            existing_file or current_file,
                            existing_line or current_line
                        )

            # Also capture direct exception lines
            exception_match = re.match(
                r"^((?:Assertion|Value|Type|Key|Index|Attribute|Name|Runtime|Import)Error.*)",
                line.strip()
            )
            if exception_match and current_test:
                error_messages[current_test] = (
                    exception_match.group(1),
                    current_file,
                    current_line
                )

        # Second pass: collect summary and create failures with extracted messages
        for line in lines:
            line_stripped = line.strip()
            if "passed" in line_stripped or "failed" in line_stripped:
                passed_match = re.search(r"(\d+) passed", line_stripped)
                failed_match = re.search(r"(\d+) failed", line_stripped)
                if passed_match:
                    passed = int(passed_match.group(1))
                if failed_match:
                    failed = int(failed_match.group(1))

            # Capture failure names (lines starting with FAILED)
            if line_stripped.startswith("FAILED"):
                test_name = line_stripped.removeprefix("FAILED").strip().split(" - ", 1)[0]
                # Look up extracted error message
                error_info = error_messages.get(test_name)
                if error_info:
                    message, file_path, line_num = error_info
                else:
                    message = "Test failed (see pytest output for details)"
                    file_path = None
                    line_num = None
                    # Try to extract file from test name
                    if "::" in test_name:
                        file_path = test_name.split("::")[0]

                failures.append(TestFailure(
                    name=test_name,
                    message=message,
                    file=file_path,
                    line=line_num,
                ))

        total = passed + failed

        # Handle special pytest exit codes when no tests were parsed
        if total == 0 and returncode != 0:
            # Exit code 5 = no tests collected (not a failure, just informational)
            if returncode == 5:
                failures.append(TestFailure(
                    name="pytest_info",
                    message="No tests collected (pytest exit code 5)",
                    file=None,
                    line=None,
                ))
                # Don't count this as a failed test - it's informational
            else:
                # Other non-zero exit codes indicate actual failures
                failures.append(TestFailure(
                    name="pytest_error",
                    message=f"pytest exited with code {returncode}",
                    file=None,
                    line=None,
                ))
                failed = 1
                total = 1  # Ensure total is consistent with failed count

        passed_names = re.findall(r"^(.+?::.+?)\s+PASSED(?:\s|$)", output, re.MULTILINE)
        return TestResult(
            passed=passed,
            failed=failed,
            total=total,
            failures=failures,
            duration_ms=duration_ms,
            passed_names=passed_names,
        )

    def _build_source_args(self, source_patterns: List[str]) -> List[str]:
        """Convert source glob patterns to coverage.py --source arguments.

        Extracts base directories from glob patterns for coverage.py's --source flag.
        coverage.py expects directory paths, not glob patterns.

        Args:
            source_patterns: Glob patterns like ["src/**/*.py", "lib/**/*.py"]

        Returns:
            List of --source arguments like ["--source=src", "--source=lib"]
        """
        sources = set()
        for pattern in source_patterns:
            # Extract base directory before any glob wildcards
            # e.g., "src/**/*.py" -> "src", "lib/utils/**/*.py" -> "lib/utils"
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
        return [f"--source={src}" for src in sorted(sources)]

    def _build_omit_args(self, exclude_patterns: List[str]) -> List[str]:
        """Convert exclude glob patterns to coverage.py --omit arguments.

        Args:
            exclude_patterns: Glob patterns like ["**/test/**", "**/__pycache__/**"]

        Returns:
            List of --omit arguments like ["--omit=**/test/**,**/__pycache__/**"]
        """
        if not exclude_patterns:
            return []
        # coverage.py accepts comma-separated patterns in a single --omit argument
        return [f"--omit={','.join(exclude_patterns)}"]

    def get_coverage(
        self,
        config: Optional[CoverageConfig] = None,
        verbose: bool = False,
    ) -> CoverageResult:
        """Collect coverage using coverage.py."""
        config = config or CoverageConfig()

        # Build coverage command
        coverage_json = self.working_dir / ".coverage.json"
        cmd = [
            sys.executable, "-m", "coverage", "run",
        ]

        if verbose:
            logger.info("Running coverage with verbose output")

        # Add source patterns (directories to include in coverage)
        if config.source_patterns:
            cmd.extend(self._build_source_args(config.source_patterns))

        # Add exclude patterns (files to omit from coverage)
        if config.exclude_patterns:
            cmd.extend(self._build_omit_args(config.exclude_patterns))

        # Add pytest runner
        cmd.extend(["-m", "pytest", "--quiet"])

        try:
            # Run tests with coverage
            cov_result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                timeout=config.timeout_seconds,
            )
            # Note: coverage run may return non-zero if tests fail, but coverage still collects
            # However, if .coverage file doesnt exist, coverage.py itself had an error

            coverage_data_file = self.working_dir / ".coverage"
            if not coverage_data_file.exists():
                # Coverage.py failed to create data file - report the actual error
                stderr_msg = cov_result.stderr.decode("utf-8", errors="replace").strip()
                error_detail = stderr_msg if stderr_msg else f"exit code {cov_result.returncode}"
                return self._create_empty_coverage_result(
                    f"Coverage data collection failed: {error_detail}",
                    config.threshold,
                )


            # Generate JSON report (only if .coverage exists)
            json_result = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", str(coverage_json)],
                cwd=str(self.working_dir),
                capture_output=True,
            )
            
            # If JSON generation failed and no coverage file exists, report error
            if json_result.returncode != 0 and not coverage_json.exists():
                return self._create_empty_coverage_result(
                    f"Coverage report generation failed (exit code {json_result.returncode})",
                    config.threshold,
                )

            # Parse coverage report
            try:
                if coverage_json.exists():
                    return self._parse_coverage_json(coverage_json, config.threshold)

                # Fall back to text report
                result = subprocess.run(
                    [sys.executable, "-m", "coverage", "report"],
                    cwd=str(self.working_dir),
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )
                if result.returncode != 0 and not result.stdout.strip():
                    return self._create_empty_coverage_result(
                        f"Coverage report failed (exit code {result.returncode})",
                        config.threshold,
                    )
                return self._parse_coverage_text(result.stdout, config.threshold)
            finally:
                # Clean up temp files
                self._cleanup_temp_files(coverage_json)

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
            logger.error(f"Invalid JSON in coverage report: {e}")
            return self._create_empty_coverage_result(f"Invalid JSON in coverage report: {e}", threshold)
        except Exception as e:
            logger.exception("Error parsing coverage JSON")
            return self._create_empty_coverage_result(str(e), threshold)

    def _parse_coverage_text(self, output: str, threshold: float) -> CoverageResult:
        """Parse coverage text report."""

        percentage = 0.0
        for line in output.split("\n"):
            # Look for TOTAL line
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
        """Clean up temporary files created during test execution.

        Args:
            primary_file: Primary temp file path (e.g., JSON report)
        """
        temp_files = [
            primary_file,
            self.working_dir / ".pytest_report.json",
            self.working_dir / ".coverage",
            self.working_dir / ".coverage.json",
        ]
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except (IOError, OSError) as e:
                logger.info(f"Cleanup error (ignored): {e}")
