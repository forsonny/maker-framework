#!/bin/bash
# MAKER Framework - Create checkpoint when subagent completes

CHECKPOINT_DIR=".maker-checkpoints"
mkdir -p "$CHECKPOINT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CHECKPOINT_FILE="$CHECKPOINT_DIR/checkpoint_$TIMESTAMP.json"

# Read subagent completion data from stdin
INPUT=$(cat)

# Save checkpoint
echo "$INPUT" > "$CHECKPOINT_FILE"
echo "Checkpoint saved: $CHECKPOINT_FILE"

exit 0
