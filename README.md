# MAKER Framework

Massively Decomposed Agentic Processes (MAD) - Break complex tasks into atomic steps with near-zero errors.

Based on the research paper: **"Solving a Million-Step LLM Task with Zero Errors"** (arXiv:2511.09030)

## Installation

### Step 1: Add the Marketplace

```bash
/plugin marketplace add forsonny/maker-framework
```

### Step 2: Install the Plugin

```bash
/plugin install maker-framework@maker-framework
```

### Step 3: Restart Claude Code

Restart to load the new plugin.

## Usage

### Automatic Mode

The MAKER orchestrator skill automatically activates when your request contains
trigger words like: create, build, implement, add, develop, make, set up,
configure, refactor, migrate.

Example:
```
Create a REST API endpoint for user authentication with JWT tokens
```

### Manual Commands

```bash
# Execute MAKER pipeline on a task
/maker-framework:maker "Build a file upload component"

# Check pipeline status
/maker-framework:maker-status

# Resume from checkpoint
/maker-framework:maker-resume

# Manage pattern cache
/maker-framework:maker-cache list
/maker-framework:maker-cache clear
/maker-framework:maker-cache inspect <pattern-id>
```

### Direct Agent Invocation

You can also request specific agents:
```
Use the maker-decomposition agent to break down this task
```

## Components

### 10 Specialized Agents

| Agent | Purpose |
|-------|---------|
| `maker-decomposition` | Breaks tasks into atomic steps |
| `maker-decomposition-discriminator` | Validates decomposition quality |
| `maker-solver` | Executes individual steps |
| `maker-red-flag` | Validates solver outputs |
| `maker-solution-discriminator` | Votes on critical steps |
| `maker-reviewer` | Final quality gate |
| `maker-complexity-estimator` | Assesses task complexity |
| `maker-cache-manager` | Manages decomposition patterns |
| `maker-checkpoint-manager` | Enables rollback/recovery |
| `maker-parallel-coordinator` | Optimizes parallel execution |

### 4 Slash Commands

| Command | Description |
|---------|-------------|
| `/maker-framework:maker` | Execute full MAKER pipeline |
| `/maker-framework:maker-status` | Check pipeline status |
| `/maker-framework:maker-resume` | Resume from checkpoint |
| `/maker-framework:maker-cache` | Manage pattern cache |

### 1 Orchestrator Skill

Auto-activates on complex development tasks and coordinates the full pipeline.

### MCP Server

QA automation server for testing integration.

### Hooks

- Post-tool validation for Write/Edit operations
- Automatic checkpointing on subagent completion

## How It Works

1. **Complexity Assessment**: Analyzes task to determine decomposition granularity
2. **Decomposition**: Breaks task into atomic, independently executable steps
3. **Validation**: Ensures decomposition is complete and correct
4. **Execution**: Runs each step with automatic validation
5. **Voting (Critical Steps)**: Multiple attempts compared for reliability
6. **Review**: Final quality gate ensures zero issues
7. **Fix Loop**: Addresses any issues and re-reviews until approved

## Key Principles

- **Maximal Agentic Decomposition (MAD)**: m=1, one atomic action per step
- **Red-flagging**: Discard responses >750 tokens or malformed
- **Voting**: First-to-ahead-by-k for critical steps
- **Checkpointing**: Enable recovery from failures
- **Caching**: Reuse successful patterns for similar tasks

## Directory Structure

```
maker-framework-plugin/
  .claude-plugin/
    plugin.json           # Plugin manifest
    marketplace.json      # Marketplace catalog
  agents/                 # 10 specialized agents
  commands/               # 4 slash commands
  skills/
    maker-orchestrator/   # Auto-activating skill
  hooks/
    hooks.json            # Validation hooks
  scripts/                # Support scripts
  .mcp.json               # QA server config
  qa_server/              # Python MCP server
  cache/                  # Pattern cache
  docs/                   # Documentation
```

## Requirements

- Claude Code CLI
- Python 3.8+ (for QA MCP server)

## License

MIT
