"""
Mocha adapter for QA MCP Server.

Provides test execution and coverage collection using Mocha
and nyc (Istanbul) for coverage.
"""

import subprocess
import sys
import shutil
import json
import time
import logging
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

from .base import BaseAdapter
from ..types import TestResult, CoverageResult, TestFailure, UncoveredLine
from ..config import TestConfig, CoverageConfig
from ..constants import MAX_UNCOVERED_LINES_TOTAL


class MochaAdapter(BaseAdapter):
    """Adapter for Mocha test framework.

    Detection:
    - mocha in package.json dependencies or devDependencies
    - .mocharc.js, .mocharc.json, or .mocharc.yml exists
    - test/ directory with .js files

    Test execution:
    - Uses npx mocha --reporter json for structured output

    Coverage:
    - Uses nyc (Istanbul) for coverage collection
    """

    name = "mocha"
    detection_patterns = [
        ".mocharc.js",
        ".mocharc.json",
        ".mocharc.yml",
        ".mocharc.yaml",
        ".mocharc.cjs",
        ".mocharc.mjs",
    ]

    def get_default_patterns(self) -> List[str]:
        """Get default test file patterns for Mocha."""
        return [
            "test/**/*.js",
            "test/**/*.ts",
            "tests/**/*.js",
            "tests/**/*.ts",
            "spec/**/*.js",
            "spec/**/*.ts",
        ]

    def _normalize_mocha_pattern(self, pattern: str) -> str:
        """Normalize a pattern for Mocha usage.

        Mocha supports glob patterns directly, but some patterns may need
        adjustment for proper matching.

        Args:
            pattern: Glob pattern (e.g., "**/*.test.js")

        Returns:
            Mocha-compatible glob pattern
        """
        # Mocha handles most glob patterns natively via node-glob
        # Just ensure patterns are in a format Mocha expects

        # If pattern doesn't start with ./ or ../ or /, make it relative
        if not pattern.startswith(("./", "../", "/", "*")):
            # Add ./ prefix for explicit relative paths
            return f"./{pattern}"

        return pattern

    def detect(self) -> bool:
        """Detect if Mocha is used in the project."""
        # Check for Mocha config files
        for pattern in self.detection_patterns:
            if (self.working_dir / pattern).exists():
                return True

        # Check package.json
        package_json = self.working_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json, "r", encoding="utf-8") as f:
                    pkg = json.load(f)

                # Check dependencies
                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})
                if "mocha" in deps or "mocha" in dev_deps:
                    return True

                # Check for mocha config in package.json
                if "mocha" in pkg:
                    return True

                # Check scripts for mocha
                scripts = pkg.get("scripts", {})
                for script in scripts.values():
                    if "mocha" in str(script).lower():
                        return True

            except (json.JSONDecodeError, IOError):
                pass

        # Check for traditional test directory
        test_dir = self.working_dir / "test"
        if test_dir.exists() and list(test_dir.glob("*.js")):
            return True

        return False

    def run_tests(
        self,
        pattern: Optional[str] = None,
        config: Optional[TestConfig] = None,
        verbose: bool = False,
    ) -> TestResult:
        """Execute tests using Mocha."""
        config = config or TestConfig()
        start_time = time.time()

        # Run pre-test hooks if configured
        if config.pre_hooks:
            hook_error = self._run_hooks(config.pre_hooks, "pre")
            if hook_error:
                return self._create_empty_test_result(hook_error)

        # Build Mocha command with verbose options if requested
        cmd = ["npx", "mocha", "--reporter", "json"]
        if verbose:
            cmd.append("--full-trace")  # Show full stack traces in verbose mode

        # Add parallel execution if configured (requires Mocha 8+)
        if config.parallel:
            cmd.append("--parallel")

        # Add pattern filter - Mocha supports glob patterns natively
        if pattern:
            cmd.append(self._normalize_mocha_pattern(pattern))
        elif config.patterns:
            # Normalize and add configured patterns
            normalized_patterns = [self._normalize_mocha_pattern(p) for p in config.patterns]
            cmd.extend(normalized_patterns)
        else:
            # Use default Mocha test patterns
            cmd.extend(self.get_default_patterns())

        # Add extra args from config
        # Security note: extra_args are already sanitized via sanitize_extra_args()
        # in load_config() to prevent shell injection attacks
        cmd.extend(config.extra_args)

        try:
            # Use shell only on Windows where npx is a batch script
            # Security: All user-controllable parts (extra_args, patterns) are sanitized
            use_shell = sys.platform == "win32"
            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=config.timeout_seconds,
                shell=use_shell,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            test_result = self._parse_mocha_json(result.stdout, duration_ms)

            # Run post-test hooks if configured (regardless of test outcome)
            if config.post_hooks:
                hook_error = self._run_hooks(config.post_hooks, "post")
                if hook_error:
                    logger.warning(f"Post-hook error (tests still reported): {hook_error}")

            return test_result

        except subprocess.TimeoutExpired:
            # Still run post-hooks on timeout
            if config.post_hooks:
                self._run_hooks(config.post_hooks, "post")
            return self._create_empty_test_result(
                f"Test execution timed out after {config.timeout_seconds} seconds"
            )
        except FileNotFoundError:
            return self._create_empty_test_result(
                "Mocha not found. Install with: npm install --save-dev mocha"
            )
        except Exception as e:
            # Still run post-hooks on error
            if config.post_hooks:
                self._run_hooks(config.post_hooks, "post")
            return self._create_empty_test_result(f"Error running Mocha: {e}")

    def _parse_mocha_json(self, output: str, duration_ms: int) -> TestResult:
        """Parse Mocha JSON reporter output."""
        try:
            # Find JSON in output (Mocha may have warnings before JSON)
            json_start = output.find("{")
            if json_start == -1:
                return self._create_empty_test_result("No JSON output from Mocha")

            json_str = output[json_start:]
            report = json.loads(json_str)

            stats = report.get("stats", {})
            passed = stats.get("passes", 0)
            failed = stats.get("failures", 0)
            total = stats.get("tests", passed + failed)

            failures: List[TestFailure] = []
            for failure in report.get("failures", []):
                failures.append(TestFailure(
                    name=failure.get("fullTitle", failure.get("title", "unknown")),
                    message=failure.get("err", {}).get("message", "Test failed"),
                    file=failure.get("file"),
                    line=None,
                ))

            # Collect passed test names for baseline tracking
            passed_names: List[str] = []
            for passed_test in report.get("passes", []):
                test_name = passed_test.get("fullTitle", passed_test.get("title", "unknown"))
                passed_names.append(test_name)

            return TestResult(
                passed=passed,
                failed=failed,
                total=total,
                failures=failures,
                duration_ms=duration_ms,
                passed_names=passed_names,
            )

        except json.JSONDecodeError as e:
            return self._create_empty_test_result(f"Error parsing Mocha output: {e}")

    def _build_nyc_coverage_args(
        self,
        source_patterns: List[str],
        exclude_patterns: List[str],
    ) -> List[str]:
        """Build nyc --include and --exclude arguments from patterns.

        nyc (Istanbul) uses --include for source files to measure and
        --exclude for files to skip.

        Args:
            source_patterns: Glob patterns for files to include in coverage
            exclude_patterns: Glob patterns for files to exclude from coverage

        Returns:
            List of nyc arguments like ["--include=src/**/*.js", "--exclude=**/test/**"]
        """
        args = []
        for pattern in source_patterns:
            args.append(f"--include={pattern}")
        for pattern in exclude_patterns:
            args.append(f"--exclude={pattern}")
        return args

    def get_coverage(
        self,
        config: Optional[CoverageConfig] = None,
        verbose: bool = False,
    ) -> CoverageResult:
        """Collect coverage using nyc (Istanbul)."""
        config = config or CoverageConfig()

        # Use default test patterns for coverage - config.source_patterns is for SOURCE files,
        # not test files. Coverage runs mocha on TEST files to measure SOURCE file coverage.
        test_patterns = self.get_default_patterns()

        cmd = [
            "npx", "nyc",
            "--reporter=json-summary",
        ]

        if verbose:
            cmd.append("--silent=false")

        # Add coverage patterns if configured
        if config.source_patterns or config.exclude_patterns:
            cmd.extend(self._build_nyc_coverage_args(
                config.source_patterns,
                config.exclude_patterns,
            ))

        # Add mocha command and test patterns
        cmd.extend(["mocha", "--reporter", "min"])
        cmd.extend(test_patterns)

        try:
            # Use shell only on Windows where npx is a batch script
            use_shell = sys.platform == "win32"
            subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                capture_output=True,
                timeout=config.timeout_seconds,
                shell=use_shell,
            )

            # Parse coverage summary
            coverage_summary = self.working_dir / "coverage" / "coverage-summary.json"
            if coverage_summary.exists():
                result = self._parse_coverage_summary(coverage_summary, config.threshold)
                self._cleanup_coverage()
                return result

            self._cleanup_coverage()
            return self._create_empty_coverage_result(
                "Coverage summary not generated. Is nyc installed?",
                config.threshold,
            )

        except subprocess.TimeoutExpired:
            self._cleanup_coverage()
            return self._create_empty_coverage_result(
                f"Coverage collection timed out after {config.timeout_seconds} seconds",
                config.threshold,
            )
        except FileNotFoundError:
            self._cleanup_coverage()
            return self._create_empty_coverage_result(
                "nyc not found. Install with: npm install --save-dev nyc",
                config.threshold,
            )
        except Exception as e:
            self._cleanup_coverage()  # Ensure cleanup on any exception
            return self._create_empty_coverage_result(str(e), config.threshold)

    def _cleanup_coverage(self) -> None:
        """Clean up coverage directory after collection."""
        coverage_dir = self.working_dir / "coverage"
        try:
            if coverage_dir.exists():
                shutil.rmtree(coverage_dir)
        except (IOError, OSError) as e:
            logger.debug(f"Failed to clean coverage directory: {e}")

    def _parse_coverage_summary(
        self,
        summary_path: Path,
        threshold: float,
    ) -> CoverageResult:
        """Parse nyc coverage summary."""
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                report = json.load(f)

            total = report.get("total", {})
            lines = total.get("lines", {})
            percentage = lines.get("pct", 0.0)

            uncovered: List[UncoveredLine] = []
            for file_path, file_data in report.items():
                if file_path == "total":
                    continue
                file_lines = file_data.get("lines", {})
                if file_lines.get("pct", 100) < 100:
                    uncovered.append(UncoveredLine(
                        file=file_path,
                        line=0,
                        content=f"Coverage: {file_lines.get('pct', 0)}%",
                    ))

            return CoverageResult(
                percentage=round(percentage, 2),
                uncovered_lines=uncovered[:MAX_UNCOVERED_LINES_TOTAL],
                meets_threshold=percentage >= threshold,
            )

        except Exception as e:
            return self._create_empty_coverage_result(str(e), threshold)
