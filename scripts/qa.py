"""Launch MAKER QA from any project, as MCP stdio or a direct local tool call."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_server.__main__ import create_server, setup_logging


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--workspace", type=Path)
    target.add_argument("--global", dest="global_mode", action="store_true",
                        help="Serve any project; each filesystem tool call must name an absolute working_dir")
    parser.add_argument("--tool", help="Omit to serve MCP over stdio")
    parser.add_argument("--arguments", default="{}", help="JSON object, or @path to a JSON file")
    args = parser.parse_args()
    raw = Path(args.arguments[1:]).read_text(encoding="utf-8") if args.arguments.startswith("@") else args.arguments
    if args.global_mode:
        os.environ["MAKER_QA_WORKSPACE_MODE"] = "explicit"
    else:
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir():
            parser.error("workspace must be a directory")
        os.environ.pop("MAKER_QA_WORKSPACE_MODE", None)
        os.chdir(workspace)
    setup_logging()
    server = create_server()
    if args.global_mode:
        for tool in server.tool_registry.values():
            schema = tool.schema.input_schema
            if "working_dir" in schema.get("properties", {}):
                properties = {**schema["properties"], "working_dir": {
                    "type": "string", "description": "Absolute target project directory for this call (required in global mode)"}}
                tool.schema.input_schema = {**schema, "properties": properties,
                                            "required": [*schema.get("required", []), "working_dir"]}
    if args.tool:
        server._initialized = True
        result = server.handle_tools_call({"name": args.tool, "arguments": json.loads(raw)})
        print(result["content"][0]["text"])
        return 1 if result.get("isError") else 0
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
