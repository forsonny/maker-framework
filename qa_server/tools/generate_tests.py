"""
generate_tests tool implementation for QA MCP Server.

Generates test stubs/templates for source files.
This is a basic implementation that creates framework-appropriate
test file templates.
"""

import logging
import os
import re
from typing import Dict, Any, List
from pathlib import Path

from ..config import load_config

logger = logging.getLogger(__name__)
from ..constants import DEFAULT_MAX_FILES
from ..utils import validate_working_dir

# MCP Tool Schema for generate_tests
GENERATE_TESTS_SCHEMA = {
    "type": "object",
    "properties": {
        "source_files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of source file paths to generate tests for",
        },
        "framework": {
            "type": "string",
            "description": "Test framework to generate tests for (use 'auto' to detect from file extensions)",
            "enum": ["auto", "pytest", "jest", "mocha", "unittest"],
        },
        "output_dir": {
            "type": "string",
            "description": "Directory to write generated test files (defaults to 'tests/')",
        },
        "style": {
            "type": "string",
            "description": "Test generation style",
            "enum": ["stub", "basic", "comprehensive"],
        },
        "write_files": {
            "type": "boolean",
            "description": "Whether to write files to disk (default: true). If false, only returns content.",
        },
        "working_dir": {
            "type": "string",
            "description": "Working directory for source file discovery (defaults to current directory)",
        },
        "max_files": {
            "type": "integer",
            "description": f"Maximum number of source files to process (default: {DEFAULT_MAX_FILES})",
            "minimum": 1,
        },
    },
    "required": ["source_files"],
    "additionalProperties": False,
}

GENERATE_TESTS_DESCRIPTION = """Generate test file templates for source files.

Creates test file stubs with appropriate structure for the specified framework.
Useful for bootstrapping test coverage for new code.

Note: Generated tests are templates that need to be filled in with actual
assertions and test logic."""


def _discover_source_files(
    working_dir: Path = None,
    max_files: int = DEFAULT_MAX_FILES,
) -> tuple:
    """Discover source files in common directories.

    Searches src/, lib/, and root for Python and JS/TS files.
    Excludes test files and common non-source directories.

    Args:
        working_dir: Directory to search in (defaults to cwd)
        max_files: Maximum number of files to return

    Returns:
        Tuple of (files: List[str], was_truncated: bool, total_found: int)
    """
    working_dir = working_dir or Path.cwd()
    source_files = []

    logger.debug("Starting source file discovery in %s (max_files=%d)", working_dir, max_files)

    # Patterns for source files
    patterns = [
        "src/**/*.py",
        "src/**/*.js",
        "src/**/*.ts",
        "lib/**/*.py",
        "lib/**/*.js",
        "app/**/*.py",     # Common Django/Flask app structure
        "app/**/*.js",
        "app/**/*.ts",
        "packages/**/*.py", # Monorepo packages
        "packages/**/*.js",
        "packages/**/*.ts",
        "*.py",  # Root level Python
        "*.js",  # Root level JavaScript
    ]

    # Patterns to exclude
    exclude_patterns = ["test_*.py", "*_test.py", "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"]

    for pattern in patterns:
        matches_for_pattern = 0
        for file_path in working_dir.glob(pattern):
            # Skip test files
            if any(file_path.match(excl) for excl in exclude_patterns):
                continue
            # Skip __pycache__ and node_modules
            if "__pycache__" in str(file_path) or "node_modules" in str(file_path):
                continue
            source_files.append(str(file_path.relative_to(working_dir)))
            matches_for_pattern += 1
        if matches_for_pattern > 0:
            logger.debug("Pattern '%s' matched %d files", pattern, matches_for_pattern)

    total_found = len(source_files)
    was_truncated = total_found > max_files

    if was_truncated:
        logger.debug("Discovery complete: %d files found, truncated to %d", total_found, max_files)
    else:
        logger.debug("Discovery complete: %d files found", total_found)

    return (source_files[:max_files], was_truncated, total_found)


def generate_tests_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle generate_tests tool invocation.

    ARCHITECTURAL DECISION: Why generate_tests does NOT use adapter_factory
    ========================================================================

    This tool intentionally does not use the adapter_factory system used by
    run_tests and get_coverage. The reasons are:

    1. TEMPLATE GENERATION vs EXECUTION: adapter_factory is designed to detect
       the test framework used by existing tests and execute them. generate_tests
       creates NEW test files, so there may be no existing framework to detect.

    2. USER INTENT MATTERS: When generating tests, the user should explicitly
       choose which framework they want the generated tests to use. Auto-detection
       would guess based on source files, but the user may want to introduce a
       new framework to the project.

    3. OUTPUT IS STATIC: The adapters execute code and parse output. Template
       generation just creates text files - no runtime detection is needed.

    4. FILE EXTENSION HEURISTIC IS SUFFICIENT: For 'auto' mode, checking if
       the source file is .py vs .js/.ts is enough to choose pytest/jest defaults.

    For actual test execution, use run_tests which leverages the full adapter
    system with proper framework detection.

    Args:
        arguments: Tool arguments from MCP call
            - source_files: List of source files to generate tests for
            - framework: Test framework to use (required)
            - output_dir: Optional output directory
            - style: Generation style (stub, basic, comprehensive)
            - write_files: Whether to write files to disk (default: True)

    Returns:
        Dict with:
            - generated_files: List of generated test file info
            - framework: Framework used
            - total_tests: Number of test stubs generated
    """
    source_files = arguments.get("source_files", [])
    framework = arguments.get("framework", "auto")
    style = arguments.get("style", "stub")
    write_files = arguments.get("write_files", True)
    working_dir_arg = arguments.get("working_dir")
    max_files = arguments.get("max_files", DEFAULT_MAX_FILES)

    # Validate max_files is a positive integer
    try:
        max_files = int(max_files)
        if max_files < 1:
            return {
                "error": f"max_files must be at least 1, got {max_files}",
                "generated_files": [],
                "framework": framework,
                "total_tests": 0,
            }
    except (TypeError, ValueError):
        return {
            "error": f"max_files must be a positive integer, got {type(max_files).__name__}",
            "generated_files": [],
            "framework": framework,
            "total_tests": 0,
        }

    # Determine and validate working directory (using shared security utility)
    is_valid, validated_path, error_msg = validate_working_dir(working_dir_arg)
    if not is_valid:
        return {
            "error": error_msg,
            "generated_files": [],
            "framework": "auto",
            "total_tests": 0,
        }
    working_dir = validated_path

    # Track if source list was truncated
    truncation_warning = None

    # Use config (now actually used)
    config = load_config(working_dir=str(working_dir), use_cache=False)
    output_dir = arguments.get("output_dir", "tests")

    # Security: Validate output_dir is within working directory
    # Resolve relative to working_dir to catch path traversal attempts like "../../../etc"
    output_dir_path = (working_dir / output_dir).resolve()
    try:
        output_dir_path.relative_to(working_dir.resolve())
    except ValueError:
        return {
            "error": f"Invalid output_dir path (must be within working directory): {output_dir}",
            "generated_files": [],
            "framework": framework,
            "total_tests": 0,
        }

    # Auto-discover source files if not provided
    if not source_files:
        source_files, was_truncated, total_found = _discover_source_files(
            working_dir=working_dir,
            max_files=max_files,
        )
        if not source_files:
            return {
                "error": "No source files specified and none discovered in src/, lib/, or root",
                "generated_files": [],
                "framework": framework,
                "total_tests": 0,
            }
        if was_truncated:
            truncation_warning = (
                f"Source file list truncated: found {total_found} files, "
                f"processing only {max_files}. Use max_files parameter to increase limit."
            )

    # Auto-detect framework based on source file extensions
    # This runs AFTER file discovery to ensure we detect from discovered files
    if framework == "auto":
        # Check first source file extension
        if source_files:
            first_file = Path(source_files[0])
            if first_file.suffix in ('.py',):
                framework = "pytest"  # Default to pytest for Python
            elif first_file.suffix in ('.js', '.ts', '.jsx', '.tsx'):
                framework = "jest"  # Default to jest for JavaScript/TypeScript
            else:
                framework = "pytest"  # Fallback to pytest

    # Validate source file paths for security
    cwd = working_dir
    for source_file in source_files:
        source_path = (working_dir / source_file).resolve()
        try:
            source_path.relative_to(cwd)
        except ValueError:
            # Path is outside cwd - reject to prevent path traversal attacks
            return {
                "error": f"Invalid source file path (must be within working directory): {source_file}",
                "generated_files": [],
                "framework": framework,
                "total_tests": 0,
            }

    generated_files = []
    total_tests = 0

    for source_file in source_files:
        source_path = (working_dir / source_file).resolve()

        if not source_path.exists():
            generated_files.append({
                "source": source_file,
                "error": "Source file not found",
                "written": False,
            })
            continue


        # Generate test file content (validation will happen in _generate functions)
        try:
            if framework in ("pytest", "unittest"):
                content, test_count = _generate_python_tests(
                    source_path, framework, style, working_dir=cwd
                )
                test_filename = f"test_{source_path.stem}.py"
            else:
                content, test_count = _generate_js_tests(
                    source_path, framework, style, working_dir=cwd
                )
                # Use correct extension based on source file type
                if source_path.suffix == ".ts":
                    test_filename = f"{source_path.stem}.test.ts"
                else:
                    test_filename = f"{source_path.stem}.test.js"
        except ValueError as e:
            generated_files.append({
                "source": source_file,
                "error": str(e),
                "written": False,
            })
            continue

        # Determine output path (using validated output_dir_path)
        output_path = output_dir_path / test_filename

        if write_files and output_path.exists():
            generated_files.append({"source": source_file, "test_file": str(output_path),
                                    "error": "Test file already exists; refusing to overwrite", "written": False})
            continue

        # Write file to disk if requested
        written = False
        write_error = None
        if write_files:
            try:
                # Create output directory if it doesn't exist
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Write the test file
                output_path.write_text(content, encoding="utf-8")
                written = True
            except (IOError, OSError) as e:
                write_error = f"Failed to write file: {e}"

        result = {
            "source": source_file,
            "test_file": str(output_path),
            "content": content,
            "test_count": test_count,
            "written": written,
        }
        if write_error:
            result["write_error"] = write_error

        generated_files.append(result)
        total_tests += test_count

    result = {
        "generated_files": generated_files,
        "framework": framework,
        "total_tests": total_tests,
    }
    if truncation_warning:
        result["warning"] = truncation_warning
    return result


def _generate_python_tests(
    source_path: Path,
    framework: str,
    style: str,
    working_dir: Path = None,
) -> tuple:
    """Generate Python test file content.

    Args:
        source_path: Path to source file
        framework: Test framework (pytest or unittest)
        style: Generation style (stub, basic, comprehensive)
        working_dir: Working directory for symlink security check

    Returns:
        Tuple of (content string, test count)

    Raises:
        ValueError: If symlink points outside working directory
    """
    # Use O_NOFOLLOW to prevent TOCTOU race conditions with symlinks
    # Open file descriptor first, then validate path safety
    try:
        fd = os.open(str(source_path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except OSError as e:
        if getattr(os, 'O_NOFOLLOW', 0) and e.errno in (20, 40):  # ENOTDIR or ELOOP
            raise ValueError(f"Security error: symbolic link detected: {source_path}")
        raise ValueError(f"Cannot read source file: {e}")

    try:
        # Read as binary first - os.fdopen takes ownership of fd and closes it
        with os.fdopen(fd, 'rb') as f:
            raw_content = f.read()
        # fd is now closed by the with block - do not close again

        # Decode with UTF-8, fall back to latin-1 for non-UTF8 files
        try:
            source_content = raw_content.decode('utf-8')
        except UnicodeDecodeError:
            source_content = raw_content.decode('latin-1')

        # After reading, validate the resolved path is safe
        if working_dir:
            resolved_path = source_path.resolve()
            try:
                resolved_path.relative_to(working_dir.resolve())
            except ValueError:
                raise ValueError(f"Security error: symlink points outside working directory: {source_path}")
    except ValueError:
        # Re-raise ValueError as-is (security errors, etc.)
        raise
    except (OSError, IOError) as e:
        raise ValueError(f"Cannot read source file: {e}")

    # Extract function and class names
    functions = re.findall(r"^def (\w+)\s*\(", source_content, re.MULTILINE)
    classes = re.findall(r"^class (\w+)\s*[:\(]", source_content, re.MULTILINE)

    # Filter out private/dunder methods
    functions = [f for f in functions if not f.startswith("_")]

    test_count = len(functions) + len(classes)
    module_name = source_path.stem

    if framework == "pytest":
        content = _generate_pytest_content(module_name, functions, classes, style)
    else:
        content = _generate_unittest_content(module_name, functions, classes, style)

    return content, test_count


def _generate_pytest_content(
    module_name: str,
    functions: List[str],
    classes: List[str],
    style: str,
) -> str:
    """Generate pytest test file content."""
    lines = [
        '"""',
        f"Tests for {module_name} module.",
        "",
        "Generated by QA MCP Server - fill in test logic.",
        '"""',
        "",
        "import pytest",
        f"# from {module_name} import *  # Uncomment and adjust import",
        "",
        "",
    ]

    # Generate test functions
    for func_name in functions:
        lines.extend([
            f"def test_{func_name}():",
            f'    """Test {func_name} function."""',
        ])

        if style == "stub":
            lines.append("    pytest.skip('Test not implemented')")
        elif style == "basic":
            lines.extend([
                f"    # Arrange",
                f"    # TODO: Set up test inputs",
                f"    ",
                f"    # Act",
                f"    # result = {func_name}(...)",
                f"    ",
                f"    # Assert",
                f"    # assert result == expected",
                f"    pytest.skip('Test not implemented')",
            ])
        else:  # comprehensive
            lines.extend([
                f"    # Test normal case",
                f"    # result = {func_name}(normal_input)",
                f"    # assert result == expected_output",
                f"    ",
                f"    # Test edge cases",
                f"    # assert {func_name}(empty_input) == ...",
                f"    # assert {func_name}(boundary_input) == ...",
                f"    ",
                f"    # Test error cases",
                f"    # with pytest.raises(ValueError):",
                f"    #     {func_name}(invalid_input)",
                f"    pytest.skip('Test not implemented')",
            ])

        lines.extend(["", ""])

    # Generate test classes
    for class_name in classes:
        lines.extend([
            f"class Test{class_name}:",
            f'    """Tests for {class_name} class."""',
            "",
            "    def test_init(self):",
            '        """Test class initialization."""',
            "        pytest.skip('Test not implemented')",
            "",
            "    def test_methods(self):",
            '        """Test class methods."""',
            "        pytest.skip('Test not implemented')",
            "",
            "",
        ])

    return "\n".join(lines)


def _generate_unittest_content(
    module_name: str,
    functions: List[str],
    classes: List[str],
    style: str,
) -> str:
    """Generate unittest test file content."""
    lines = [
        '"""',
        f"Tests for {module_name} module.",
        "",
        "Generated by QA MCP Server - fill in test logic.",
        '"""',
        "",
        "import unittest",
        f"# from {module_name} import *  # Uncomment and adjust import",
        "",
        "",
        f"class Test{module_name.title().replace('_', '')}(unittest.TestCase):",
        f'    """Test cases for {module_name}."""',
        "",
    ]

    # Generate test methods for functions
    for func_name in functions:
        lines.extend([
            f"    def test_{func_name}(self):",
            f'        """Test {func_name} function."""',
            f"        self.skipTest('Not implemented')",
            "",
        ])

    # Generate test methods for classes
    for class_name in classes:
        lines.extend([
            f"    def test_{class_name.lower()}_init(self):",
            f'        """Test {class_name} initialization."""',
            f"        self.skipTest('Not implemented')",
            "",
        ])

    lines.extend([
        "",
        "if __name__ == '__main__':",
        "    unittest.main()",
        "",
    ])

    return "\n".join(lines)


def _generate_js_tests(
    source_path: Path,
    framework: str,
    style: str,
    working_dir: Path = None,
) -> tuple:
    """Generate JavaScript test file content.

    Args:
        source_path: Path to source file
        framework: Test framework (jest or mocha)
        style: Generation style (stub, basic, comprehensive)
        working_dir: Working directory for symlink security check

    Returns:
        Tuple of (content string, test count)

    Raises:
        ValueError: If symlink points outside working directory
    """
    # Use O_NOFOLLOW to prevent TOCTOU race conditions with symlinks
    # Open file descriptor first, then validate path safety
    try:
        fd = os.open(str(source_path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except OSError as e:
        if getattr(os, 'O_NOFOLLOW', 0) and e.errno in (20, 40):  # ENOTDIR or ELOOP
            raise ValueError(f"Security error: symbolic link detected: {source_path}")
        raise ValueError(f"Cannot read source file: {e}")

    try:
        # Read as binary first - os.fdopen takes ownership of fd and closes it
        with os.fdopen(fd, 'rb') as f:
            raw_content = f.read()
        # fd is now closed by the with block - do not close again

        # Decode with UTF-8, fall back to latin-1 for non-UTF8 files
        try:
            source_content = raw_content.decode('utf-8')
        except UnicodeDecodeError:
            source_content = raw_content.decode('latin-1')

        # After reading, validate the resolved path is safe
        if working_dir:
            resolved_path = source_path.resolve()
            try:
                resolved_path.relative_to(working_dir.resolve())
            except ValueError:
                raise ValueError(f"Security error: symlink points outside working directory: {source_path}")
    except ValueError:
        # Re-raise ValueError as-is (security errors, etc.)
        raise
    except (OSError, IOError) as e:
        raise ValueError(f"Cannot read source file: {e}")

    # Extract exported functions
    functions = re.findall(
        r"(?:export\s+(?:async\s+)?function|export\s+const)\s+(\w+)",
        source_content
    )
    functions += re.findall(
        r"module\.exports\s*=\s*\{([^}]+)\}",
        source_content
    )

    # Also find top-level function declarations
    functions += re.findall(
        r"^(?:async\s+)?function\s+(\w+)\s*\(",
        source_content,
        re.MULTILINE
    )

    # Deduplicate and filter
    functions = list(set([f.strip() for f in functions if f.strip()]))
    functions = [f for f in functions if not f.startswith("_")]

    test_count = max(len(functions), 1)
    module_name = source_path.stem

    if framework == "jest":
        content = _generate_jest_content(module_name, functions, style)
    else:
        content = _generate_mocha_content(module_name, functions, style)

    return content, test_count


def _generate_jest_content(
    module_name: str,
    functions: List[str],
    style: str,
) -> str:
    """Generate Jest test file content."""
    lines = [
        "/**",
        f" * Tests for {module_name}",
        " *",
        " * Generated by QA MCP Server - fill in test logic.",
        " */",
        "",
        f"// const {{ ... }} = require('./{module_name}');  // Uncomment and adjust",
        "",
        f"describe('{module_name}', () => {{",
    ]

    if functions:
        for func_name in functions:
            lines.extend([
                f"  describe('{func_name}', () => {{",
                f"    it('should work correctly', () => {{",
            ])

            if style == "stub":
                lines.append("      // TODO: Implement test")
            else:
                lines.extend([
                    "      // Arrange",
                    "      // const input = ...;",
                    "",
                    "      // Act",
                    f"      // const result = {func_name}(input);",
                    "",
                    "      // Assert",
                    "      // expect(result).toBe(expected);",
                    "      expect(true).toBe(true);  // Placeholder",
                ])

            lines.extend([
                "    });",
                "  });",
                "",
            ])
    else:
        lines.extend([
            "  it('should be tested', () => {",
            "    // TODO: Add tests",
            "    expect(true).toBe(true);",
            "  });",
            "",
        ])

    lines.append("});")
    lines.append("")

    return "\n".join(lines)


def _generate_mocha_content(
    module_name: str,
    functions: List[str],
    style: str,
) -> str:
    """Generate Mocha test file content."""
    lines = [
        "/**",
        f" * Tests for {module_name}",
        " *",
        " * Generated by QA MCP Server - fill in test logic.",
        " */",
        "",
        "const { expect } = require('chai');",
        f"// const {{ ... }} = require('./{module_name}');  // Uncomment and adjust",
        "",
        f"describe('{module_name}', function() {{",
    ]

    if functions:
        for func_name in functions:
            lines.extend([
                f"  describe('{func_name}', function() {{",
                f"    it('should work correctly', function() {{",
            ])

            if style == "stub":
                lines.append("      // TODO: Implement test")
            else:
                lines.extend([
                    "      // Arrange",
                    "      // const input = ...;",
                    "",
                    "      // Act",
                    f"      // const result = {func_name}(input);",
                    "",
                    "      // Assert",
                    "      // expect(result).to.equal(expected);",
                    "      expect(true).to.be.true;  // Placeholder",
                ])

            lines.extend([
                "    });",
                "  });",
                "",
            ])
    else:
        lines.extend([
            "  it('should be tested', function() {",
            "    // TODO: Add tests",
            "    expect(true).to.be.true;",
            "  });",
            "",
        ])

    lines.append("});")
    lines.append("")

    return "\n".join(lines)
