"""
aggregate_qa_report tool implementation for QA MCP Server.

Collects and aggregates QA results from multiple validation stages
into a unified report format for cross-stage quality assessment.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# MCP Tool Schema for aggregate_qa_report
AGGREGATE_QA_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "stage_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stage_name": {
                        "type": "string",
                        "description": "Name of the validation stage (e.g., 'decomposition', 'solver', 'review')",
                    },
                    "passed": {
                        "type": "integer",
                        "description": "Number of passed checks/tests",
                        "minimum": 0,
                    },
                    "failed": {
                        "type": "integer",
                        "description": "Number of failed checks/tests",
                        "minimum": 0,
                    },
                    "skipped": {
                        "type": "integer",
                        "description": "Number of skipped checks/tests",
                        "minimum": 0,
                    },
                    "details": {
                        "type": "object",
                        "description": "Stage-specific details (test names, coverage %, etc.)",
                    },
                },
                "required": ["stage_name", "passed", "failed"],
            },
            "description": "List of QA results from each validation stage",
        },
        "include_summary": {
            "type": "boolean",
            "description": "Include summary statistics in output (default: true)",
        },
        "format": {
            "type": "string",
            "enum": ["full", "compact", "summary_only"],
            "description": "Output format level (default: full)",
        },
    },
    "required": ["stage_results"],
    "additionalProperties": False,
}

AGGREGATE_QA_REPORT_DESCRIPTION = """Aggregate QA results from multiple validation stages into unified report.

Collects results from:
- Decomposition validation (check_prd_alignment)
- Solver execution (run_tests if applicable)
- Final review (all QA checks)

Returns unified report with:
- Overall pass/fail status
- Per-stage breakdown
- Aggregate metrics (pass rate, coverage)
- Recommendations for improvement

Use in maker-reviewer Check 9 for comprehensive QA summary."""


def _calculate_summary(stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics from stage results.

    Args:
        stage_results: List of stage result dicts

    Returns:
        Summary dict with totals and rates
    """
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for stage in stage_results:
        total_passed += stage.get("passed", 0)
        total_failed += stage.get("failed", 0)
        total_skipped += stage.get("skipped", 0)

    total_checks = total_passed + total_failed
    pass_rate = (total_passed / total_checks * 100) if total_checks > 0 else 100.0

    return {
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "total_checks": total_checks,
        "pass_rate": round(pass_rate, 2),
    }


def _determine_overall_status(summary: Dict[str, Any], stage_results: List[Dict[str, Any]]) -> str:
    """Determine overall QA status based on summary and stage results.

    Args:
        summary: Calculated summary statistics
        stage_results: Original stage results

    Returns:
        Status string: "PASS", "FAIL", or "PARTIAL"
    """
    if summary["total_failed"] == 0:
        return "PASS"

    # Check if any critical stage failed completely
    for stage in stage_results:
        details = stage.get("details", {})
        is_critical = details.get("critical", False)
        stage_passed = stage.get("passed", 0)
        stage_failed = stage.get("failed", 0)

        # Critical stage with any failure = overall FAIL
        if is_critical and stage_failed > 0:
            return "FAIL"

        # Non-critical stage with all failures = concerning but not blocking
        if stage_passed == 0 and stage_failed > 0:
            return "FAIL"

    # Some failures but not critical = PARTIAL
    if summary["pass_rate"] >= 70:
        return "PARTIAL"

    return "FAIL"


def _extract_stage_details(stage: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalize stage details for reporting.

    Args:
        stage: Stage result dict

    Returns:
        Normalized details dict
    """
    details = stage.get("details", {})
    normalized = {
        "stage_name": stage.get("stage_name", "unknown"),
        "passed": stage.get("passed", 0),
        "failed": stage.get("failed", 0),
        "skipped": stage.get("skipped", 0),
    }

    # Extract common detail fields
    if "coverage_percentage" in details:
        normalized["coverage"] = details["coverage_percentage"]

    if "alignment_score" in details:
        normalized["prd_alignment"] = details["alignment_score"]

    if "failures" in details:
        # Limit failure details for readability
        failures = details["failures"]
        normalized["failure_summary"] = [
            {"name": f.get("name", "unknown"), "reason": f.get("reason", f.get("message", "")[:100])}
            for f in failures[:10]  # Max 10 failures
        ]

    if "regressions" in details:
        normalized["regressions"] = len(details["regressions"])

    return normalized


def _generate_recommendations(
    summary: Dict[str, Any],
    stages: List[Dict[str, Any]],
    overall_status: str,
) -> List[str]:
    """Generate improvement recommendations based on QA results.

    Args:
        summary: Summary statistics
        stages: Processed stage results
        overall_status: Overall status string

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Overall status recommendations
    if overall_status == "FAIL":
        recommendations.append("CRITICAL: QA validation failed - address failing checks before proceeding")
    elif overall_status == "PARTIAL":
        recommendations.append("WARNING: Some QA checks failed - review and address before release")

    # Pass rate recommendations
    if summary["pass_rate"] < 70:
        recommendations.append(f"Pass rate ({summary['pass_rate']}%) is below 70% threshold")
    elif summary["pass_rate"] < 90:
        recommendations.append(f"Pass rate ({summary['pass_rate']}%) is moderate - aim for 90%+")

    # Stage-specific recommendations
    for stage in stages:
        stage_name = stage.get("stage_name", "unknown")

        # Coverage recommendations
        if "coverage" in stage:
            coverage = stage["coverage"]
            if coverage < 70:
                recommendations.append(f"{stage_name}: Coverage ({coverage}%) is below 70% threshold")

        # PRD alignment recommendations
        if "prd_alignment" in stage:
            alignment = stage["prd_alignment"]
            if alignment < 70:
                recommendations.append(f"{stage_name}: PRD alignment ({alignment}%) is low - review requirements")

        # Regression recommendations
        if "regressions" in stage and stage["regressions"] > 0:
            recommendations.append(f"{stage_name}: {stage['regressions']} regression(s) detected - investigate")

        # Failure recommendations
        if stage.get("failed", 0) > 0 and "failure_summary" in stage:
            recommendations.append(f"{stage_name}: {stage['failed']} check(s) failed")

    return recommendations[:10]  # Limit to 10 recommendations


def aggregate_qa_report_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle aggregate_qa_report tool invocation.

    Args:
        arguments: Tool arguments from MCP call
            - stage_results: List of stage result dicts (required)
            - include_summary: Whether to include summary stats (default: true)
            - format: Output format level (default: full)

    Returns:
        Dict with:
            - summary: Aggregate statistics (total_passed, total_failed, pass_rate)
            - stages: List of processed stage results
            - overall_status: PASS, FAIL, or PARTIAL
            - recommendations: List of improvement suggestions
            - timestamp: ISO timestamp of report generation
    """
    stage_results = arguments.get("stage_results", [])
    include_summary = arguments.get("include_summary", True)
    output_format = arguments.get("format", "full")

    # Validate input
    if not stage_results:
        return {
            "error": "No stage results provided",
            "summary": {"total_passed": 0, "total_failed": 0, "pass_rate": 0},
            "stages": [],
            "overall_status": "FAIL",
            "recommendations": ["No QA results to aggregate - run QA checks first"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Validate stage result format
    for i, stage in enumerate(stage_results):
        if not isinstance(stage, dict):
            return {
                "error": f"Stage result at index {i} is not a dict",
                "summary": {"total_passed": 0, "total_failed": 0, "pass_rate": 0},
                "stages": [],
                "overall_status": "FAIL",
                "recommendations": ["Fix stage result format"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        if "stage_name" not in stage:
            stage["stage_name"] = f"stage_{i + 1}"
        if "passed" not in stage:
            stage["passed"] = 0
        if "failed" not in stage:
            stage["failed"] = 0

    # Calculate summary
    summary = _calculate_summary(stage_results)

    # Process stages
    processed_stages = [_extract_stage_details(s) for s in stage_results]

    # Determine overall status
    overall_status = _determine_overall_status(summary, stage_results)

    # Generate recommendations
    recommendations = _generate_recommendations(summary, processed_stages, overall_status)

    # Build response based on format
    timestamp = datetime.now(timezone.utc).isoformat()

    if output_format == "summary_only":
        return {
            "summary": summary if include_summary else None,
            "overall_status": overall_status,
            "timestamp": timestamp,
        }

    if output_format == "compact":
        return {
            "summary": summary if include_summary else None,
            "stages": [
                {"name": s["stage_name"], "passed": s["passed"], "failed": s["failed"]}
                for s in processed_stages
            ],
            "overall_status": overall_status,
            "timestamp": timestamp,
        }

    # Full format
    return {
        "summary": summary if include_summary else None,
        "stages": processed_stages,
        "overall_status": overall_status,
        "recommendations": recommendations,
        "timestamp": timestamp,
    }
