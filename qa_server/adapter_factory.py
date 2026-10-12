"""
Adapter factory for automatic test framework selection.

Provides get_adapter() function that returns the appropriate
test framework adapter based on configuration or auto-detection.
"""

import logging
from typing import List, Optional

from pathlib import Path

logger = logging.getLogger(__name__)

from .config import QAConfig
from .types import QAUnavailableResult
from .adapters.base import BaseAdapter
from .adapters.pytest_adapter import PytestAdapter
from .adapters.jest_adapter import JestAdapter
from .adapters.mocha_adapter import MochaAdapter
from .adapters.unittest_adapter import UnittestAdapter


# Adapter registry in priority order for auto-detection
ADAPTER_CLASSES = [
    PytestAdapter,
    JestAdapter,
    MochaAdapter,
    UnittestAdapter,
]

# Framework name to adapter class mapping
ADAPTER_MAP = {
    "pytest": PytestAdapter,
    "jest": JestAdapter,
    "mocha": MochaAdapter,
    "unittest": UnittestAdapter,
}


class NoSupportedFramework(ValueError):
    """Auto-detection found no supported test runner."""

    def to_result(self) -> QAUnavailableResult:
        return QAUnavailableResult(
            status="unavailable",
            code="NO_SUPPORTED_TEST_FRAMEWORK",
            message=str(self),
            tests_executed=0,
        )


def get_adapter(
    config: Optional[QAConfig] = None,
    working_dir: Optional[str] = None,
) -> BaseAdapter:
    """Get the appropriate test framework adapter.

    Args:
        config: QA configuration. If config.test.framework is set to
               a specific framework, that adapter is returned.
               If set to "auto" (default), auto-detection is used.
        working_dir: Working directory for test execution.
                    Defaults to current directory.

    Returns:
        BaseAdapter instance for the detected or configured framework

    Raises:
        ValueError: If specified framework is unknown
        NoSupportedFramework: If auto-detection finds no supported framework

    Priority for auto-detection:
        1. pytest (most common Python framework)
        2. jest (most common JS framework)
        3. mocha (alternative JS framework)
        4. unittest (Python fallback)
    """
    config = config or QAConfig()
    framework = config.test.framework.lower()

    # If specific framework requested, use it
    if framework != "auto":
        if framework not in ADAPTER_MAP:
            raise ValueError(
                f"Unknown test framework: {framework}. "
                f"Supported: {', '.join(ADAPTER_MAP.keys())}"
            )
        adapter_class = ADAPTER_MAP[framework]
        return adapter_class(working_dir=working_dir)

    # Auto-detect framework
    for adapter_class in ADAPTER_CLASSES:
        adapter = adapter_class(working_dir=working_dir)
        try:
            if adapter.detect():
                logger.debug(f"Detected test framework: {adapter.name}")
                return adapter
        except Exception as e:
            logger.warning(f"Error detecting {adapter.name}: {e}")
            continue

    raise NoSupportedFramework(
        f"No supported test framework detected in {working_dir or Path.cwd()}. "
        "No tests were executed. Configure or explicitly select a supported "
        "framework (pytest, jest, mocha, unittest) if the project uses one; "
        "otherwise verify the project with its own test or manual acceptance workflow."
    )


def detect_all_frameworks(working_dir: Optional[str] = None) -> List[str]:
    """Detect all test frameworks present in the project.

    Args:
        working_dir: Working directory to scan

    Returns:
        List of detected framework names
    """
    detected = []
    for adapter_class in ADAPTER_CLASSES:
        adapter = adapter_class(working_dir=working_dir)
        try:
            if adapter.detect():
                detected.append(adapter.name)
        except Exception as e:
            logger.warning(f"Error detecting {adapter.name}: {e}")
            continue
    return detected
