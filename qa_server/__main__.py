"""
Entry point for the QA MCP Server.

Usage:
    python -m qa_server

Environment variables:
    QA_CONFIG_PATH: Path to qa-config.yaml (default: ./qa-config.yaml)
    QA_REPORTS_DIR: Directory for reports and baselines (default: ./qa-reports)
    QA_LOG_LEVEL: Logging level (default: INFO)
"""

import logging
import os
import sys

from .server import MCPServer
from .tools.run_tests import (
    run_tests_handler,
    RUN_TESTS_SCHEMA,
    RUN_TESTS_DESCRIPTION,
)
from .tools.get_coverage import (
    get_coverage_handler,
    GET_COVERAGE_SCHEMA,
    GET_COVERAGE_DESCRIPTION,
)
from .tools.check_regressions import (
    check_regressions_handler,
    CHECK_REGRESSIONS_SCHEMA,
    CHECK_REGRESSIONS_DESCRIPTION,
)
from .tools.generate_tests import (
    generate_tests_handler,
    GENERATE_TESTS_SCHEMA,
    GENERATE_TESTS_DESCRIPTION,
)
from .tools.check_prd_alignment import (
    check_prd_alignment_handler,
    CHECK_PRD_ALIGNMENT_SCHEMA,
    CHECK_PRD_ALIGNMENT_DESCRIPTION,
)
from .tools.aggregate_qa_report import (
    aggregate_qa_report_handler,
    AGGREGATE_QA_REPORT_SCHEMA,
    AGGREGATE_QA_REPORT_DESCRIPTION,
)


# Ping tool definitions
PING_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
PING_DESCRIPTION = "Health check to verify server is running and responsive"


def ping_handler(arguments: dict) -> dict:
    """Handle ping requests for health checks."""
    return {"status": "ok", "message": "QA MCP Server is running"}


def setup_logging() -> None:
    """Configure logging for the QA MCP Server.

    Reads QA_LOG_LEVEL environment variable to set log level.
    Default level is INFO. Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    log_level = os.environ.get("QA_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def create_server() -> MCPServer:
    """Create and configure the QA MCP Server.

    Returns:
        Configured MCPServer instance with all tools registered
    """
    server = MCPServer(name="maker-qa", version="1.2.1")

    # Register run_tests tool
    server.register_tool(
        name="run_tests",
        handler=run_tests_handler,
        description=RUN_TESTS_DESCRIPTION,
        input_schema=RUN_TESTS_SCHEMA,
    )

    # Register get_coverage tool
    server.register_tool(
        name="get_coverage",
        handler=get_coverage_handler,
        description=GET_COVERAGE_DESCRIPTION,
        input_schema=GET_COVERAGE_SCHEMA,
    )

    # Register check_regressions tool
    server.register_tool(
        name="check_regressions",
        handler=check_regressions_handler,
        description=CHECK_REGRESSIONS_DESCRIPTION,
        input_schema=CHECK_REGRESSIONS_SCHEMA,
    )

    # Register generate_tests tool
    server.register_tool(
        name="generate_tests",
        handler=generate_tests_handler,
        description=GENERATE_TESTS_DESCRIPTION,
        input_schema=GENERATE_TESTS_SCHEMA,
    )

    # Register check_prd_alignment tool
    server.register_tool(
        name="check_prd_alignment",
        handler=check_prd_alignment_handler,
        description=CHECK_PRD_ALIGNMENT_DESCRIPTION,
        input_schema=CHECK_PRD_ALIGNMENT_SCHEMA,
    )

    # Register aggregate_qa_report tool
    server.register_tool(
        name="aggregate_qa_report",
        handler=aggregate_qa_report_handler,
        description=AGGREGATE_QA_REPORT_DESCRIPTION,
        input_schema=AGGREGATE_QA_REPORT_SCHEMA,
    )

    # Register ping tool
    server.register_tool(
        name="ping",
        handler=ping_handler,
        description=PING_DESCRIPTION,
        input_schema=PING_SCHEMA,
    )

    return server


def main():
    """Main entry point for QA MCP Server."""
    setup_logging()
    server = create_server()

    # Run the server (blocks until EOF on stdin)
    try:
        server.run()
    except Exception as e:
        print(f"[QA MCP] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
