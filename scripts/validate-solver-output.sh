#!/bin/bash
# MAKER Framework - Validate solver output format

# Read solver output from stdin
INPUT=$(cat)

# Check for required fields
ERRORS=""

# Check for TASK_ID
if ! echo "$INPUT" | grep -q '\[TASK_ID\]'; then
    ERRORS="${ERRORS}Missing [TASK_ID] field\n"
fi

# Check for STEP
if ! echo "$INPUT" | grep -q '\[STEP\]'; then
    ERRORS="${ERRORS}Missing [STEP] field\n"
fi

# Check for STATUS
if ! echo "$INPUT" | grep -q '\[STATUS\]'; then
    ERRORS="${ERRORS}Missing [STATUS] field\n"
else
    # Validate STATUS value
    STATUS=$(echo "$INPUT" | grep '\[STATUS\]' | sed 's/.*\[STATUS\]\s*//' | tr -d '[:space:]')
    if [ "$STATUS" != "SUCCESS" ] && [ "$STATUS" != "BLOCKED" ]; then
        ERRORS="${ERRORS}Invalid STATUS value: $STATUS (must be SUCCESS or BLOCKED)\n"
    fi
fi

# Check for ACTION TAKEN section
if ! echo "$INPUT" | grep -q 'ACTION TAKEN'; then
    ERRORS="${ERRORS}Missing ACTION TAKEN section\n"
fi

# Check for OUTPUT STATE section
if ! echo "$INPUT" | grep -q 'OUTPUT STATE'; then
    ERRORS="${ERRORS}Missing OUTPUT STATE section\n"
fi

# Count approximate tokens (words * 1.3)
WORD_COUNT=$(echo "$INPUT" | wc -w)
TOKEN_ESTIMATE=$((WORD_COUNT * 13 / 10))

if [ $TOKEN_ESTIMATE -gt 750 ]; then
    ERRORS="${ERRORS}Response too long: ~$TOKEN_ESTIMATE tokens (limit: 750)\n"
fi

# Output results
if [ -n "$ERRORS" ]; then
    echo "VALIDATION FAILED:"
    echo -e "$ERRORS"
    exit 1
else
    echo "VALIDATION PASSED"
    echo "Token estimate: ~$TOKEN_ESTIMATE"
    exit 0
fi
