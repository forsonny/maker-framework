#!/bin/bash
# MAKER Framework - Validate output from Write/Edit operations

# Read hook input from stdin
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0  # No file path, skip validation
fi

# Basic validation - file exists and is not empty
if [ -f "$FILE_PATH" ]; then
    if [ -s "$FILE_PATH" ]; then
        echo "Validation passed: $FILE_PATH exists and has content"
        exit 0
    else
        echo "Warning: $FILE_PATH is empty" >&2
        exit 0  # Warning but don't block
    fi
fi

exit 0
