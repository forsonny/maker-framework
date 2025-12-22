"""
Jest adapter for QA MCP Server.

Provides test execution and coverage collection using Jest.
"""

import logging
import subprocess
import sys
import shutil
import json
import time
from typing import Optional, List
from pathlib import Path

from .base import BaseAdapter

from ..types import TestResult, CoverageResult, TestFailure, UncoveredLine
from ..config import TestConfig, CoverageConfig
from ..constants import MAX_UNCOVERED_LINES_TOTAL

logger = logging.getLogger(__name__)


class JestAdapter(BaseAdapter):
    """Adapter for Jest test framework.

    Detection:
    - jest in package.json dependencies or devDependencies
    - jest.config.js or jest.config.ts exists
    - *.test.js or *.spec.js files exist

    Test execution:
    - Uses npx jest --json for structured output

    Coverage:
    - Uses jest --coverage for built-in coverage
    """

    name = "jest"
    detection_patterns = [
        "jest.config.js",
        "jest.config.ts",
        "jest.config.mjs",
        "jest.config.cjs",
    ]

    def get_default_patterns(self) -> List[str]:
        """Get default test file patterns for Jest."""
        return ["**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts"]

    def _convert_glob_to_jest_pattern(self, pattern: str) -> str:
        """Convert a glob pattern to Jest testPathPattern regex.

        Jest's --testPathPattern expects a regex, not a glob pattern.
        This converts common glob patterns to equivalent regex patterns.

        Args:
            pattern: Glob pattern (e.g., "**/*.test.js")

        Returns:
            Jest-compatible regex pattern (e.g., "\\.test\\.js$")
        """
        # If it's already a regex-like pattern (contains regex chars), use as-is
        if pattern.startswith("^") or pattern.endswith("$"):
            return pattern

        # Use placeholders to avoid replacement order issues
        DOUBLE_STAR_SLASH = "\x00DSS\x00"
        DOUBLE_STAR = "\x00DS\x00"
        SINGLE_STAR = "\x00SS\x00"
        QUESTION = "\x00Q\x00"

        # Replace glob patterns with placeholders first
        regex = pattern.replace("**/", DOUBLE_STAR_SLASH)
        regex = regex.replace("**", DOUBLE_STAR)
        regex = regex.replace("*", SINGLE_STAR)
        regex = regex.replace("?", QUESTION)

        # Escape ALL regex special characters: . + ^ $ { } [ ] | ( ) \
        # Order matters: escape backslash first to avoid double-escaping
        for char in r'\.[]+^${}|()':
            regex = regex.replace(char, "\\" + char)

        # Restore glob patterns with proper regex equivalents
        regex = regex.replace(DOUBLE_STAR_SLASH, "(.*/)?")
        regex = regex.replace(DOUBLE_STAR, ".*")
        regex = regex.replace(SINGLE_STAR, "[^/]*")
        regex = regex.replace(QUESTION, ".")

        # Anchor to end if it ends with a file extension
        if any(regex.endswith(ext) for ext in [r"\.js", r"\.ts", r"\.jsx", r"\.tsx"]):
            regex = regex + "$"

        return regex

    def detect(self) -> bool:
        """Detect if Jest is used in the project."""
        # Check for Jest config files
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
                if "jest" in deps or "jest" in dev_deps:
                    return True

                # Check for jest config in package.json
                if "jest" in pkg:
                    return True

                # Check scripts for jest
                scripts = pkg.get("scripts", {})
                for script in scripts.values():
                    if "jest" in str(script).lower():
                        return True

            except (json.JSONDecodeError, IOError):
                pass

        # Check for test files
        test_patterns = ["**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts"]
        for pattern in test_patterns:
            if list(self.working_dir.glob(pattern)):
                return True

        return False

    def run_tests(
        self,
        pattern: Optional[str] = None,
        config: Optional[TestConfig] = None,
        verbose: bool = False,
    ) -> TestResult:
        """Execute tests using Jest."""
        config = config or TestConfig()
        start_time = time.time()

        # Run pre-test hooks if configured
        if config.pre_hooks:
            hook_error = self._run_hooks(config.pre_hooks, "pre")
            if hook_error:
                return self._create_empty_test_result(hook_error)

        # Build Jest command with verbose flag if requested
        cmd = ["npx", "jest", "--json", "--passWithNoTests"]
        if verbose:
            cmd.append("--verbose")

        # Add parallel execution if configured (Jest runs parallel by default)
        if config.parallel:
            cmd.append("--maxWorkers=auto")
        else:
            # Run tests sequentially for deterministic output
            cmd.append("--runInBand")

        # Add pattern filter using --testPathPattern for proper Jest pattern handling
        # Jest expects regex patterns via --testPathPattern, not glob patterns as arguments
        if pattern:
            jest_pattern = self._convert_glob_to_jest_pattern(pattern)
            cmd.extend(["--testPathPattern", jest_pattern])
        elif config.patterns:
            # Combine multiple patterns into OR regex
            jest_patterns = [self._convert_glob_to_jest_pattern(p) for p in config.patterns]
            combined_pattern = "|".join(f"({p})" for p in jest_patterns)
            cmd.extend(["--testPathPattern", combined_pattern])
        # If no patterns specified, let Jest use its defaults (don't add patterns)

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

            # Jest outputs JSON to stdout
            test_result = self._parse_jest_json(result.stdout, duration_ms)

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
                "Jest not found. Install with: npm install --save-dev jest"
            )
        except Exception as e:
            # Still run post-hooks on error
            if config.post_hooks:
                self._run_hooks(config.post_hooks, "post")
            return self._create_empty_test_result(f"Error running Jest: {e}")

    def _parse_jest_json(self, output: str, duration_ms: int) -> TestResult:
        """Parse Jest JSON output."""
        try:
            # Jest may output non-JSON before the actual JSON
            # Find the JSON object in the output
            json_start = output.find("{")
            if json_start == -1:
                return self._create_empty_test_result("No JSON output from Jest")

            json_str = output[json_start:]
            report = json.loads(json_str)

            passed = report.get("numPassedTests", 0)
            failed = report.get("numFailedTests", 0)
            total = report.get("numTotalTests", passed + failed)

            failures: List[TestFailure] = []
            passed_names: List[str] = []

            for test_result in report.get("testResults", []):
                for assertion in test_result.get("assertionResults", []):
                    status = assertion.get("status")
                    test_name = assertion.get("fullName", assertion.get("title", "unknown"))

                    if status == "failed":
                        failures.append(TestFailure(
                            name=test_name,
                            message="\n".join(assertion.get("failureMessages", ["Test failed"])),
                            file=test_result.get("name"),
                            line=None,
                        ))
                    elif status == "passed":
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
            return self._create_empty_test_result(f"Error parsing Jest output: {e}")

    def _build_coverage_from_patterns(
        self,
        source_patterns: List[str],
        exclude_patterns: List[str],
    ) -> List[str]:
        """Build Jest --collectCoverageFrom arguments from patterns.

        Jest uses collectCoverageFrom with glob patterns. Exclusions are
        specified by prefixing patterns with '!' (negation).

        Args:
            source_patterns: Glob patterns for files to include in coverage
            exclude_patterns: Glob patterns for files to exclude from coverage

        Returns:
            List of --collectCoverageFrom arguments
        """
        args = []
        # Add source patterns (files to include)
        for pattern in source_patterns:
            args.extend(["--collectCoverageFrom", pattern])
        # Add exclude patterns with negation prefix
        for pattern in exclude_patterns:
            # Jest uses ! prefix for exclusions
            negated = pattern if pattern.startswith("!") else f"!{pattern}"
            args.extend(["--collectCoverageFrom", negated])
        return args

    def get_coverage(
        self,
        config: Optional[CoverageConfig] = None,
        verbose: bool = False,
    ) -> CoverageResult:
        """Collect coverage using Jest."""
        config = config or CoverageConfig()

        cmd = [
            "npx", "jest",
            "--coverage",
            "--coverageReporters=json-summary",
            "--passWithNoTests",
        ]

        if verbose:
            cmd.append("--verbose")

        # Add coverage patterns if configured
        if config.source_patterns or config.exclude_patterns:
            cmd.extend(self._build_coverage_from_patterns(
                config.source_patterns,
                config.exclude_patterns,
            ))

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
                "Coverage summary not generated",
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
                "Jest not found. Install with: npm install --save-dev jest",
                config.threshold,
            )
        except Exception as e:
            self._cleanup_coverage()
            return self._create_empty_coverage_result(str(e), config.threshold)

    def _parse_coverage_summary(
        self,
        summary_path: Path,
        threshold: float,
    ) -> CoverageResult:
        """Parse Jest coverage summary."""
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
                        line=0,  # Jest summary doesn't include line numbers
                        content=f"Coverage: {file_lines.get('pct', 0)}%",
                    ))

            return CoverageResult(
                percentage=round(percentage, 2),
                uncovered_lines=uncovered[:MAX_UNCOVERED_LINES_TOTAL],  # Limit results
                meets_threshold=percentage >= threshold,
            )

        except Exception as e:
            return self._create_empty_coverage_result(str(e), threshold)

    def _cleanup_coverage(self) -> None:
        """Clean up coverage directory after collection."""
        coverage_dir = self.working_dir / "coverage"
        try:
            if coverage_dir.exists():
                shutil.rmtree(coverage_dir)
        except (IOError, OSError) as e:
            logger.debug(f"Failed to clean coverage directory: {e}")
