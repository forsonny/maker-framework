# MAKER Framework Plugin

This plugin provides the MAKER (Massively Decomposed Agentic Processes) framework for Claude Code.

## Orchestration Instructions

The detailed orchestration logic is maintained in the main framework. Import it here to keep in sync:

@../maker-framework/CLAUDE.md

## Plugin-Specific Notes

- Agents are defined in `agents/` directory
- Slash commands are in `commands/` directory
- The orchestrator skill is in `skills/maker-orchestrator/`
- Prompt templates are in `skills/maker-orchestrator/prompts.md`

## Quick Reference

All subagent invocations MUST use the fully qualified name format:
- `maker-framework:maker-solver`
- `maker-framework:maker-decomposition`
- `maker-framework:maker-red-flag`
- `maker-framework:maker-reviewer`
- etc.

See the imported CLAUDE.md above for complete orchestration details.
