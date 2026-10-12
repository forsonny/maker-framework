"""Shared utility functions for the QA server."""

import os
import unicodedata
from pathlib import Path
from typing import Tuple, Optional


def validate_working_dir(working_dir: Optional[str]) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Validate and resolve a working directory path with security checks.

    Local mode allows cwd and QA_ALLOWED_PATHS. The global Codex launcher uses
    explicit mode: each call must select an absolute project directory; paths
    used by its handlers are then bounded to that selected project.

    Args:
        working_dir: The directory path to validate. If None, uses current working directory.

    Returns:
        A tuple of (is_valid, resolved_path, error_message):
        - is_valid: True if the path is valid and allowed
        - resolved_path: The resolved absolute Path if valid, None otherwise
        - error_message: Description of the error if invalid, None otherwise

    Examples:
        >>> is_valid, path, error = validate_working_dir(None)
        >>> is_valid
        True
        >>> is_valid, path, error = validate_working_dir("/some/disallowed/path")
        >>> is_valid
        False
    """
    explicit_workspace = os.environ.get("MAKER_QA_WORKSPACE_MODE") == "explicit"
    if working_dir is None:
        if explicit_workspace:
            return (False, None, "Global QA calls require an absolute working_dir for the target project")
        return (True, Path.cwd(), None)

    # Normalize Unicode to prevent bypass attacks with different Unicode forms
    normalized_dir = unicodedata.normalize('NFC', working_dir)
    if explicit_workspace and not Path(normalized_dir).is_absolute():
        return (False, None, "Global QA calls require an absolute working_dir for the target project")
    
    # Resolve to absolute path
    try:
        resolved_path = Path(normalized_dir).resolve()
    except (OSError, ValueError) as e:
        return (False, None, f"Invalid path: {e}")

    # Check if path exists and is a directory
    if not resolved_path.exists():
        return (False, None, f"Path does not exist: {resolved_path}")

    if not resolved_path.is_dir():
        return (False, None, f"Path is not a directory: {resolved_path}")

    if explicit_workspace:
        return (True, resolved_path, None)

    # Security check: validate path is allowed
    cwd = Path.cwd().resolve()

    # Check if path is within current working directory
    try:
        resolved_path.relative_to(cwd)
        return (True, resolved_path, None)
    except ValueError:
        # Path is not within cwd, check allowed paths
        pass

    # Check QA_ALLOWED_PATHS environment variable
    allowed_paths_env = os.environ.get("QA_ALLOWED_PATHS", "")
    if allowed_paths_env:
        allowed_paths = [
            Path(p.strip()).resolve()
            for p in allowed_paths_env.split(",")
            if p.strip()
        ]

        for allowed_path in allowed_paths:
            try:
                resolved_path.relative_to(allowed_path)
                return (True, resolved_path, None)
            except ValueError:
                continue

    # Path is outside allowed directories
    return (
        False,
        None,
        f"Security error: Path '{resolved_path}' is outside allowed directories. "
        f"Allowed: current working directory ({cwd}) or paths in QA_ALLOWED_PATHS."
    )
