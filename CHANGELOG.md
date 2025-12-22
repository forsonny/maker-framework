# Changelog

All notable changes to the MAKER Framework plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.7] - 2025-12-22

### Fixed

- **Critical**: Fixed MCP server `maker-qa` failing to start due to incorrect path configuration
  - `cwd` was incorrectly set to `${CLAUDE_PLUGIN_ROOT}/qa_server` (inside the package)
  - `PYTHONPATH` was also pointing inside the package
  - Python couldn't find the `qa_server` module when running `-m qa_server` from inside itself
  - Changed both paths to `${CLAUDE_PLUGIN_ROOT}` (the parent directory containing the package)

## [1.0.6] - 2025-12-22

### Fixed

- **Critical**: Added missing `tools` frontmatter to all 10 agents
  - Without tool restrictions, agents had access to ALL tools, causing role boundary violations
  - Decomposition agent was writing files instead of just returning decomposition plans
- Synced plugin agents with original framework subagents to ensure consistency

### Changed

- Agent frontmatter now includes:
  - `tools:` - Restricts which tools each agent can use
  - `model:` - Specifies model (inherit or haiku)
  - `permissionMode:` - Controls permission behavior

### Agent Tool Restrictions

| Agent | Tools |
|-------|-------|
| maker-decomposition | Read, Grep, Glob |
| maker-solver | Read, Edit, Write, Bash, Grep, Glob |
| maker-red-flag | Read, Grep |
| maker-reviewer | Read, Grep, Glob, WebFetch, WebSearch, Bash, mcp__claude-qa__* |
| maker-decomposition-discriminator | Read, Grep, Glob, mcp__claude-qa__check_prd_alignment |
| maker-solution-discriminator | Read, Grep, Glob |
| maker-complexity-estimator | Read, Grep, Glob |
| maker-checkpoint-manager | Read, Write, Bash, Glob |
| maker-parallel-coordinator | Read, Grep, Glob |
| maker-cache-manager | Read, Grep, Glob, Write |

## [1.0.5] - 2025-12-22

### Fixed

- **Critical**: Removed Write, Edit, Bash from orchestrator skill allowed-tools to prevent direct file operations
- Orchestrator was bypassing the MAKER workflow by writing files directly instead of delegating to maker-solver
- Added explicit "Orchestration Only" constraints forbidding direct file modifications
- All file operations now properly flow through maker-solver subagent

### Changed

- `commands/maker.md` allowed-tools reduced to `Read, Glob, Grep`
- `skills/maker-orchestrator/SKILL.md` allowed-tools reduced to `Read, Glob, Grep`
- Added detailed forbidden actions documentation to prevent workflow bypass

## [1.0.4] - 2025-12-22

### Added

- Added color property to agent frontmatter for visual distinction in Claude Code UI
  - maker-decomposition: green
  - maker-solver: orange
  - maker-red-flag: red
  - maker-reviewer: yellow
  - maker-cache-manager: blue

## [1.0.3] - 2025-12-22

### Fixed

- Fixed QA MCP server failing to start on Windows with `[WinError 10038]` socket error
- Changed `select` module detection from import-based to explicit platform check since Windows can import `select` but it only works with sockets, not stdin

## [1.0.2] - 2025-12-22

### Fixed

- Made hook scripts cross-platform by converting from bash (.sh) to Node.js (.js)
- Fixes issue where .sh scripts would open in text editor on Windows instead of executing

### Added

- `scripts/checkpoint-on-complete.js` - Cross-platform checkpoint script
- `scripts/validate-output.js` - Cross-platform validation script

## [1.0.1] - 2025-12-22

### Fixed

- Fixed marketplace.json source field from `"."` to `"./"` to comply with Claude Code plugin schema validation

## [1.0.0] - 2025-12-22

### Added

- Initial plugin release
- 10 specialized agents:
  - `maker-decomposition` - Task decomposition using MAD
  - `maker-decomposition-discriminator` - Decomposition validation
  - `maker-solver` - Atomic step execution
  - `maker-red-flag` - Output validation
  - `maker-solution-discriminator` - Voting for critical steps
  - `maker-reviewer` - Final quality gate
  - `maker-complexity-estimator` - Task complexity assessment
  - `maker-cache-manager` - Pattern cache management
  - `maker-checkpoint-manager` - Rollback/recovery support
  - `maker-parallel-coordinator` - Parallel execution planning
- 4 slash commands:
  - `/maker-framework:maker` - Full pipeline execution
  - `/maker-framework:maker-status` - Status checking
  - `/maker-framework:maker-resume` - Checkpoint resume
  - `/maker-framework:maker-cache` - Cache management
- Orchestrator skill with automatic activation
- QA MCP server integration
- Post-tool validation hooks
- Subagent completion checkpointing
- Pattern caching for decomposition reuse
- Comprehensive documentation

### Technical Details

- Based on arXiv:2511.09030 "Solving a Million-Step LLM Task with Zero Errors"
- Implements Maximal Agentic Decomposition (MAD) with m=1
- Cost scaling: Theta(s ln s) vs exponential for coarser decomposition
- Red-flag threshold: 750 tokens
- Review loop: Continues until zero issues found

## [Unreleased]

### Planned

- Enhanced parallel execution support
- Improved cache hit rate algorithms
- Additional QA integration tools
- Performance metrics dashboard
