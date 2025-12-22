"""
QA MCP Tools.

Each module provides a handler function for an MCP tool that integrates
with maker-reviewer's Check 8 QA Engine validation.
"""

from .run_tests import run_tests_handler
from .get_coverage import get_coverage_handler
from .check_regressions import check_regressions_handler
from .generate_tests import generate_tests_handler
from .check_prd_alignment import check_prd_alignment_handler
from .aggregate_qa_report import aggregate_qa_report_handler

__all__ = [
    "run_tests_handler",
    "get_coverage_handler",
    "check_regressions_handler",
    "generate_tests_handler",
    "check_prd_alignment_handler",
    "aggregate_qa_report_handler",
]
