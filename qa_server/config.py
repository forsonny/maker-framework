"""
Configuration handling for QA MCP Server.

Loads configuration from qa-config.yaml and provides typed access
to settings for test execution, coverage, and regression analysis.
"""

import logging
import os
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Maximum config file size to prevent DoS via large YAML files (1 MB)
MAX_CONFIG_FILE_SIZE = 1 * 1024 * 1024

# Pattern for dangerous shell metacharacters that could enable command injection
# Added backslash, quotes, and null bytes to prevent escaping and injection
_DANGEROUS_CHARS_PATTERN = re.compile(r'[;|&$`(){}<>\n\r\\\'"\x00]')


def sanitize_extra_args(args: List[str]) -> List[str]:
    """Sanitize extra_args to prevent command injection.

    Filters out arguments containing dangerous shell metacharacters
    that could be exploited when passed to subprocess.run().

    Args:
        args: List of command line arguments to sanitize

    Returns:
        List of safe arguments with dangerous ones filtered out

    Security:
        This function blocks the following dangerous characters that could
        enable shell command injection attacks:

        - ; (command separator)
        - | (pipe)
        - & (background/AND operator)
        - $ (variable expansion)
        - ` (command substitution)
        - ( ) (subshell)
        - { } (brace expansion)
        - < > (redirection)
        - newlines (command separator)

        Arguments containing any of these characters are silently dropped
        with a warning logged.

    Examples:
        >>> sanitize_extra_args(["--verbose", "-x"])
        ['--verbose', '-x']

        >>> sanitize_extra_args(["--flag; rm -rf /"])  # Blocked
        []

        >>> sanitize_extra_args(["--config=$(cat /etc/passwd)"])  # Blocked
        []

    Note:
        This is used automatically when loading extra_args from qa-config.yaml.
        Direct API callers should use this function when passing user input.
    """
    safe_args = []
    for arg in args:
        if not isinstance(arg, str):
            logger.warning("Rejected non-string extra_arg: %r", arg)
            continue

        # Check for dangerous shell metacharacters
        if _DANGEROUS_CHARS_PATTERN.search(arg):
            logger.warning(
                "Rejected extra_arg containing dangerous characters: %r", arg
            )
            continue

        safe_args.append(arg)

    return safe_args


# Pattern for dangerous command substitution that must be blocked even in hooks
# Added $var pattern, escaped variants, and improved coverage
_DANGEROUS_SUBSTITUTION_PATTERN = re.compile(r'\$\(|`|\$\{|\$[a-zA-Z_]|\\\$|\\\`')


def sanitize_hooks(hooks: List[str]) -> List[str]:
    """Sanitize pre/post hooks while allowing shell command chaining.

    Unlike sanitize_extra_args(), this function allows shell operators like
    && | ; that are commonly needed for hook commands (e.g., "npm run build && npm test").

    Args:
        hooks: List of shell command strings to sanitize

    Returns:
        List of safe hook commands with dangerous ones filtered out

    Security:
        This function BLOCKS dangerous patterns that enable arbitrary code execution:
        - $() (command substitution)
        - `` (backtick command substitution)
        - ${} (variable expansion with braces)

        This function ALLOWS shell operators needed for hooks:
        - && (AND operator for chaining)
        - || (OR operator for fallback)
        - | (pipe)
        - ; (command separator)
        - > < (redirection)

        Hooks are intended to be shell commands defined by the project owner,
        not arbitrary user input. They run with the same privileges as the test
        framework, so allowing shell operators is acceptable for legitimate use cases
        like "npm install && npm test" or "make clean; make test".

    Examples:
        >>> sanitize_hooks(["npm run build && npm test"])
        ['npm run build && npm test']

        >>> sanitize_hooks(["echo $(whoami)"])  # Blocked - command substitution
        []

        >>> sanitize_hooks(["echo `id`"])  # Blocked - backtick substitution
        []

    Warning:
        Hooks should only be configured by trusted project maintainers, not by
        untrusted user input. This function provides defense-in-depth but is not
        a substitute for restricting who can modify qa-config.yaml.
    """
    safe_hooks = []
    for hook in hooks:
        if not isinstance(hook, str):
            logger.warning("Rejected non-string hook: %r", hook)
            continue

        # Normalize Unicode to prevent bypasses with homoglyphs
        normalized_hook = unicodedata.normalize('NFC', hook)

        # Block dangerous command substitution patterns
        if _DANGEROUS_SUBSTITUTION_PATTERN.search(normalized_hook):
            logger.warning(
                "Rejected hook containing dangerous command substitution: %r", hook
            )
            continue

        # Block control characters (but not newlines within quoted strings)
        if '\r' in normalized_hook or '\x00' in normalized_hook:
            logger.warning(
                "Rejected hook containing control characters: %r", hook
            )
            continue

        safe_hooks.append(hook)

    return safe_hooks


def _validate_positive_int(value: Any, field_name: str, default: int, min_value: int = 1) -> int:
    """Validate and return a positive integer value.

    Args:
        value: The value to validate
        field_name: Name of the field (for logging)
        default: Default value if validation fails
        min_value: Minimum acceptable value (default: 1)

    Returns:
        Valid positive integer
    """
    try:
        int_value = int(value)
        if int_value < min_value:
            logger.warning(
                "%s value %s is below minimum %d, using %d",
                field_name, value, min_value, default
            )
            return default
        return int_value
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s value %r, using default %d",
            field_name, value, default
        )
        return default


@dataclass
class TestConfig:
    """Configuration for test execution."""
    framework: str = "auto"  # auto, pytest, jest, mocha, unittest, command
    command: Optional[List[str]] = None  # Executable and arguments; never shell-split.
    patterns: List[str] = field(default_factory=list)  # Use each framework's discovery defaults.
    timeout_seconds: int = 300
    parallel: bool = False
    extra_args: List[str] = field(default_factory=list)
    # Pre-test hooks: shell commands to run before test execution (e.g., database reset)
    pre_hooks: List[str] = field(default_factory=list)
    # Post-test hooks: shell commands to run after test execution (e.g., cleanup)
    post_hooks: List[str] = field(default_factory=list)


@dataclass
class CoverageConfig:
    """Configuration for coverage analysis.

    Attributes:
        threshold: Minimum coverage percentage required (0-100). Default: 70.0
        source_patterns: Glob patterns for source files to include in coverage.
            Patterns are translated to framework-specific arguments:
            - pytest/unittest: --source arguments for coverage.py
            - Jest: --collectCoverageFrom arguments
            - Mocha: --include arguments for nyc
        exclude_patterns: Glob patterns for files to exclude from coverage.
            Patterns are translated to framework-specific arguments:
            - pytest/unittest: --omit arguments for coverage.py
            - Jest: Negated patterns in --collectCoverageFrom (e.g., !**/test/**)
            - Mocha: --exclude arguments for nyc
        timeout_seconds: Maximum time for coverage collection. Default: 300
    """
    threshold: float = 70.0
    source_patterns: List[str] = field(default_factory=lambda: [
        "src/**/*.py",
        "src/**/*.js",
        "src/**/*.ts",
        "lib/**/*.py",
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/test/**",
        "**/tests/**",
        "**/__pycache__/**",
        "**/node_modules/**",
    ])
    timeout_seconds: int = 300  # Coverage collection timeout


@dataclass
class RegressionConfig:
    """Configuration for regression analysis."""
    baseline_file: str = "qa-reports/baseline.json"
    auto_update_baseline: bool = False
    ignore_flaky: bool = True
    flaky_threshold: int = 3  # Number of flips before marking flaky


@dataclass
class QAConfig:
    """Main configuration for QA MCP Server."""
    test: TestConfig = field(default_factory=TestConfig)
    coverage: CoverageConfig = field(default_factory=CoverageConfig)
    regression: RegressionConfig = field(default_factory=RegressionConfig)
    reports_dir: str = "qa-reports"
    verbose: bool = False


# Module-level config cache with thread safety
_config_cache: Optional[QAConfig] = None
_config_cache_path: Optional[str] = None
_config_lock = threading.Lock()


def load_config(path: Optional[str] = None, use_cache: bool = True, working_dir: Optional[str] = None) -> QAConfig:
    """Load QA configuration from YAML file.

    Args:
        path: Path to config file. If None, checks QA_CONFIG_PATH env var,
              then falls back to ./qa-config.yaml
        use_cache: If True, return cached config when available (default: True)

    Returns:
        QAConfig instance with loaded or default values

    Note:
        If PyYAML is not installed and a config file exists, logs a warning
        and returns default configuration instead of raising an error.
    """
    global _config_cache, _config_cache_path

    # Determine config path
    if path is None:
        path = os.environ.get("QA_CONFIG_PATH") or str(Path(working_dir or ".") / "qa-config.yaml")

    # Acquire lock for loading (no quick-check outside lock to avoid TOCTOU race)
    with _config_lock:
        # Check cache inside lock for thread safety
        if use_cache and _config_cache is not None and _config_cache_path == path:
            return _config_cache

        config_path = Path(path)

        # Return defaults if no config file exists
        if not config_path.exists():
            config = QAConfig()
            if use_cache:
                _config_cache = config
                _config_cache_path = path
            return config

        # Check file size to prevent DoS via large YAML files
        file_size = config_path.stat().st_size
        if file_size > MAX_CONFIG_FILE_SIZE:
            logger.warning(
                "Config file %s is too large (%d bytes, max %d bytes). Using default configuration.",
                config_path, file_size, MAX_CONFIG_FILE_SIZE
            )
            config = QAConfig()
            if use_cache:
                _config_cache = config
                _config_cache_path = path
            return config

        # Check YAML availability - graceful fallback to defaults
        if not YAML_AVAILABLE:
            logger.warning(
                "PyYAML is not installed. Config file %s exists but cannot be loaded. "
                "Using default configuration. Install PyYAML with: pip install pyyaml",
                config_path
            )

            config = QAConfig()
            if use_cache:
                _config_cache = config
                _config_cache_path = path
            return config

        # Load and parse YAML
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            # Log detailed YAML parsing error for debugging
            error_details = str(e)
            if hasattr(e, 'problem_mark') and e.problem_mark is not None:
                mark = e.problem_mark
                error_details = f"{e.problem} at line {mark.line + 1}, column {mark.column + 1}"
            logger.error(
                "YAML parsing error in config file %s: %s",
                config_path, error_details
            )
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}")
        except (IOError, UnicodeDecodeError) as e:
            raise ValueError(f"Cannot read config file {config_path}: {e}")

        # Build config from YAML data
        test_data = data.get("test", {})
        coverage_data = data.get("coverage", {})
        regression_data = data.get("regression", {})

        # Validate timeout_seconds
        test_timeout = _validate_positive_int(
            test_data.get("timeout_seconds", 300),
            "test.timeout_seconds",
            300
        )

        # Validate framework enum
        framework = test_data.get("framework", "auto")
        allowed_frameworks = ["auto", "pytest", "jest", "mocha", "unittest", "command"]
        if framework not in allowed_frameworks:
            logger.warning(
                "Invalid test framework '%s' in config, using 'auto'. Allowed: %s",
                framework, allowed_frameworks
            )
            framework = "auto"
        
        # Validate glob patterns
        def validate_glob_patterns(patterns_list, field_name):
            """Validate that all patterns in a list are valid glob syntax."""
            import fnmatch
            import re
            valid_patterns = []
            for pattern in patterns_list:
                try:
                    fnmatch.translate(pattern)  # Test if valid glob
                    valid_patterns.append(pattern)
                except (re.error, ValueError):
                    logger.warning(
                        "Invalid glob pattern '%s' in %s, skipping",
                        pattern, field_name
                    )
            return valid_patterns
        
        patterns = validate_glob_patterns(
            test_data.get("patterns", TestConfig().patterns), 
            "test.patterns"
        )
        
        command = test_data.get("command")
        if "command" in test_data and (
            not isinstance(command, list) or not command
            or any(not isinstance(arg, str) or "\0" in arg for arg in command)
            or not command[0].strip()
        ):
            raise ValueError("test.command must be a nonempty list of strings beginning with an executable")

        test_config = TestConfig(
            framework=framework,
            command=command,
            patterns=patterns,
            timeout_seconds=test_timeout,
            parallel=test_data.get("parallel", False),
            extra_args=sanitize_extra_args(test_data.get("extra_args", [])),
            pre_hooks=sanitize_hooks(test_data.get("pre_hooks", [])),
            post_hooks=sanitize_hooks(test_data.get("post_hooks", [])),
        )

        # Validate and clamp coverage threshold to 0-100 range
        raw_threshold = coverage_data.get("threshold", 70.0)
        try:
            threshold_value = float(raw_threshold)
            if threshold_value < 0:
                logger.warning(
                    "Coverage threshold %s is below 0, clamping to 0.0",
                    raw_threshold
                )
                threshold_value = 0.0
            elif threshold_value > 100:
                logger.warning(
                    "Coverage threshold %s exceeds 100, clamping to 100.0",
                    raw_threshold
                )
                threshold_value = 100.0
        except (TypeError, ValueError):
            logger.warning(
                "Invalid coverage threshold value %r, using default 70.0",
                raw_threshold
            )
            threshold_value = 70.0

        # Validate coverage timeout
        coverage_timeout = _validate_positive_int(
            coverage_data.get("timeout_seconds", 300),
            "coverage.timeout_seconds",
            300
        )

        # Validate coverage patterns
        source_patterns = validate_glob_patterns(
            coverage_data.get("source_patterns", CoverageConfig().source_patterns),
            "coverage.source_patterns"
        )
        exclude_patterns = validate_glob_patterns(
            coverage_data.get("exclude_patterns", CoverageConfig().exclude_patterns),
            "coverage.exclude_patterns"
        )
        
        coverage_config = CoverageConfig(
            threshold=threshold_value,
            source_patterns=source_patterns,
            exclude_patterns=exclude_patterns,
            timeout_seconds=coverage_timeout,
        )

        # Validate flaky_threshold
        flaky_threshold = _validate_positive_int(
            regression_data.get("flaky_threshold", 3),
            "regression.flaky_threshold",
            3
        )

        regression_config = RegressionConfig(
            baseline_file=regression_data.get("baseline_file", "qa-reports/baseline.json"),
            auto_update_baseline=regression_data.get("auto_update_baseline", False),
            ignore_flaky=regression_data.get("ignore_flaky", True),
            flaky_threshold=flaky_threshold,
        )

        # Get reports_dir with QA_REPORTS_DIR env var override
        reports_dir = os.environ.get(
            "QA_REPORTS_DIR",
            data.get("reports_dir", "qa-reports")
        )

        config = QAConfig(
            test=test_config,
            coverage=coverage_config,
            regression=regression_config,
            reports_dir=reports_dir,
            verbose=data.get("verbose", False),
        )

        # Cache the config
        if use_cache:
            _config_cache = config
            _config_cache_path = path

        return config


def clear_config_cache() -> None:
    """Clear the config cache. Useful for testing or reloading config."""
    global _config_cache, _config_cache_path
    with _config_lock:
        _config_cache = None
        _config_cache_path = None
