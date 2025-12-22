"""
check_prd_alignment tool implementation for QA MCP Server.

Verifies that implementation code aligns with Product Requirements Document (PRD).
Analyzes source files against PRD requirements and returns alignment score with
detailed findings.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..config import load_config
from ..utils import validate_working_dir
from ..constants import DEFAULT_MAX_FILES

logger = logging.getLogger(__name__)


# MCP Tool Schema for check_prd_alignment
CHECK_PRD_ALIGNMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "prd_path": {
            "type": "string",
            "description": "Path to the PRD file (markdown, txt, or other text format)",
        },
        "implementation_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of implementation file paths to check. If not provided, auto-discovers source files.",
        },
        "working_dir": {
            "type": "string",
            "description": "Working directory for file discovery (defaults to current directory)",
        },
        "requirement_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Custom regex patterns to extract requirements from PRD (optional)",
        },
        "max_files": {
            "type": "integer",
            "description": f"Maximum number of implementation files to analyze (default: {DEFAULT_MAX_FILES})",
            "minimum": 1,
        },
    },
    "required": ["prd_path"],
    "additionalProperties": False,
}

CHECK_PRD_ALIGNMENT_DESCRIPTION = """Check implementation alignment with PRD requirements.

Analyzes source code against Product Requirements Document to verify:
- All requirements from PRD are addressed in implementation
- Implementation matches expected behavior described in PRD
- No major gaps between requirements and implementation

Returns alignment score (0-100) with detailed findings.
Use in maker-decomposition-discriminator to validate task plans against PRD.
Use in maker-reviewer to verify completed work meets requirements."""


def _extract_requirements(prd_content: str, custom_patterns: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Extract requirements from PRD content.

    Looks for common requirement patterns:
    - "shall", "must", "should", "will" statements
    - Numbered requirements (1., 2., etc.)
    - Bullet points with requirement keywords
    - Headers followed by requirement descriptions

    Args:
        prd_content: Raw PRD file content
        custom_patterns: Optional custom regex patterns to use

    Returns:
        List of requirement dicts with 'id', 'text', and 'type' fields
    """
    requirements = []

    # Default patterns for requirement extraction
    patterns = custom_patterns or [
        # Must/shall/should statements
        r'(?:must|shall|should|will)\s+([^.!?\n]+[.!?]?)',
        # Numbered requirements like "1. The system..."
        r'^\s*(\d+\.)\s+([^\n]+)',
        # Requirements with REQ- prefix
        r'(REQ-\d+)[:\s]+([^\n]+)',
        # Features section items
        r'^\s*[-*]\s*\*\*([^*]+)\*\*[:\s]*([^\n]+)',
        # Goal/Objective statements
        r'(?:goal|objective)[:\s]+([^\n]+)',
    ]

    req_id = 1
    seen_texts = set()  # Deduplicate requirements

    for pattern in patterns:
        try:
            matches = re.finditer(pattern, prd_content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Get the full match or first group
                if match.lastindex and match.lastindex >= 2:
                    req_text = f"{match.group(1)} {match.group(2)}".strip()
                elif match.lastindex:
                    req_text = match.group(1).strip()
                else:
                    req_text = match.group(0).strip()

                # Skip if too short or already seen
                if len(req_text) < 10 or req_text.lower() in seen_texts:
                    continue

                seen_texts.add(req_text.lower())
                requirements.append({
                    "id": f"REQ-{req_id:03d}",
                    "text": req_text[:500],  # Limit length
                    "type": "functional",
                })
                req_id += 1

        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            continue

    return requirements


def _analyze_implementation(
    impl_path: Path,
    requirements: List[Dict[str, str]],
    working_dir: Path,
) -> Tuple[List[str], List[str]]:
    """Analyze implementation file for requirement coverage.

    Args:
        impl_path: Path to implementation file
        requirements: List of requirements to check against
        working_dir: Working directory for security validation

    Returns:
        Tuple of (matched_req_ids, unmatched_req_ids)
    """
    matched = []

    # Validate path security
    try:
        resolved = impl_path.resolve()
        resolved.relative_to(working_dir.resolve())
    except ValueError:
        logger.warning(f"Skipping file outside working directory: {impl_path}")
        return [], []

    # Read implementation file
    try:
        if impl_path.suffix in ('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs'):
            content = impl_path.read_text(encoding='utf-8', errors='replace')
        else:
            return [], []
    except (IOError, OSError) as e:
        logger.warning(f"Cannot read implementation file {impl_path}: {e}")
        return [], []

    content_lower = content.lower()

    # Check each requirement for evidence in implementation
    for req in requirements:
        req_text = req["text"].lower()

        # Extract key terms from requirement (nouns, verbs)
        key_terms = re.findall(r'\b([a-z]{4,})\b', req_text)
        key_terms = [t for t in key_terms if t not in {
            'must', 'shall', 'should', 'will', 'that', 'this', 'with',
            'from', 'have', 'been', 'being', 'when', 'where', 'which'
        }]

        if not key_terms:
            continue

        # Check if enough key terms appear in implementation
        matches_found = sum(1 for term in key_terms if term in content_lower)
        match_ratio = matches_found / len(key_terms) if key_terms else 0

        if match_ratio >= 0.5:  # At least 50% of key terms found
            matched.append(req["id"])

    return matched, []


def _discover_source_files(working_dir: Path, max_files: int = DEFAULT_MAX_FILES) -> List[Path]:
    """Discover source files in common directories.

    Args:
        working_dir: Directory to search
        max_files: Maximum files to return

    Returns:
        List of source file paths
    """
    source_files = []
    patterns = [
        "src/**/*.py", "src/**/*.js", "src/**/*.ts",
        "lib/**/*.py", "lib/**/*.js", "lib/**/*.ts",
        "app/**/*.py", "app/**/*.js", "app/**/*.ts",
        "*.py", "*.js", "*.ts",
    ]

    exclude_patterns = {"test_", "_test.", ".test.", ".spec.", "__pycache__", "node_modules"}

    for pattern in patterns:
        for path in working_dir.glob(pattern):
            if any(excl in str(path) for excl in exclude_patterns):
                continue
            source_files.append(path)
            if len(source_files) >= max_files:
                break
        if len(source_files) >= max_files:
            break

    return source_files


def check_prd_alignment_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle check_prd_alignment tool invocation.

    Args:
        arguments: Tool arguments from MCP call
            - prd_path: Path to PRD file (required)
            - implementation_paths: Optional list of implementation files
            - working_dir: Optional working directory
            - requirement_patterns: Optional custom extraction patterns
            - max_files: Optional max files to analyze

    Returns:
        Dict with:
            - alignment_score: 0-100 score
            - matched_requirements: List of matched requirement IDs with evidence
            - unmatched_requirements: List of unmatched requirement IDs
            - recommendations: List of improvement suggestions
            - total_requirements: Total requirements found in PRD
            - files_analyzed: Number of implementation files analyzed
    """
    prd_path_str = arguments.get("prd_path")
    impl_paths = arguments.get("implementation_paths", [])
    working_dir_arg = arguments.get("working_dir")
    custom_patterns = arguments.get("requirement_patterns")
    max_files = arguments.get("max_files", DEFAULT_MAX_FILES)

    # Validate working directory
    is_valid, working_dir, error_msg = validate_working_dir(working_dir_arg)
    if not is_valid:
        return {
            "error": error_msg,
            "alignment_score": 0,
            "matched_requirements": [],
            "unmatched_requirements": [],
            "recommendations": [],
            "total_requirements": 0,
            "files_analyzed": 0,
        }

    # Validate and read PRD file
    prd_path = Path(prd_path_str)
    if not prd_path.is_absolute():
        prd_path = working_dir / prd_path

    try:
        prd_path = prd_path.resolve()
        prd_path.relative_to(working_dir.resolve())
    except ValueError:
        return {
            "error": f"PRD path must be within working directory: {prd_path_str}",
            "alignment_score": 0,
            "matched_requirements": [],
            "unmatched_requirements": [],
            "recommendations": [],
            "total_requirements": 0,
            "files_analyzed": 0,
        }

    if not prd_path.exists():
        return {
            "error": f"PRD file not found: {prd_path_str}",
            "alignment_score": 0,
            "matched_requirements": [],
            "unmatched_requirements": [],
            "recommendations": [],
            "total_requirements": 0,
            "files_analyzed": 0,
        }

    try:
        prd_content = prd_path.read_text(encoding='utf-8', errors='replace')
    except (IOError, OSError) as e:
        return {
            "error": f"Cannot read PRD file: {e}",
            "alignment_score": 0,
            "matched_requirements": [],
            "unmatched_requirements": [],
            "recommendations": [],
            "total_requirements": 0,
            "files_analyzed": 0,
        }

    # Extract requirements from PRD
    requirements = _extract_requirements(prd_content, custom_patterns)

    if not requirements:
        return {
            "warning": "No requirements found in PRD. Check PRD format or provide custom patterns.",
            "alignment_score": 100,  # No requirements = fully aligned
            "matched_requirements": [],
            "unmatched_requirements": [],
            "recommendations": ["PRD appears to contain no extractable requirements"],
            "total_requirements": 0,
            "files_analyzed": 0,
        }

    # Get implementation files
    if impl_paths:
        impl_files = [working_dir / p if not Path(p).is_absolute() else Path(p) for p in impl_paths]
    else:
        impl_files = _discover_source_files(working_dir, max_files)

    if not impl_files:
        return {
            "warning": "No implementation files found",
            "alignment_score": 0,
            "matched_requirements": [],
            "unmatched_requirements": [r["id"] for r in requirements],
            "recommendations": ["Add implementation files to analyze"],
            "total_requirements": len(requirements),
            "files_analyzed": 0,
        }

    # Analyze each implementation file
    all_matched = set()

    for impl_path in impl_files[:max_files]:
        matched, _ = _analyze_implementation(impl_path, requirements, working_dir)
        all_matched.update(matched)

    # Calculate results
    matched_reqs = [r for r in requirements if r["id"] in all_matched]
    unmatched_reqs = [r for r in requirements if r["id"] not in all_matched]

    alignment_score = int((len(matched_reqs) / len(requirements)) * 100) if requirements else 100

    # Generate recommendations
    recommendations = []
    if unmatched_reqs:
        recommendations.append(f"Address {len(unmatched_reqs)} unimplemented requirements")
        for req in unmatched_reqs[:5]:  # Top 5
            recommendations.append(f"Missing: {req['text'][:100]}...")

    if alignment_score < 70:
        recommendations.append("Alignment score is below 70% - significant gaps in implementation")
    elif alignment_score < 90:
        recommendations.append("Alignment score is moderate - review unmatched requirements")

    return {
        "alignment_score": alignment_score,
        "matched_requirements": [
            {"id": r["id"], "text": r["text"]} for r in matched_reqs
        ],
        "unmatched_requirements": [
            {"id": r["id"], "text": r["text"]} for r in unmatched_reqs
        ],
        "recommendations": recommendations,
        "total_requirements": len(requirements),
        "files_analyzed": len(impl_files[:max_files]),
    }
