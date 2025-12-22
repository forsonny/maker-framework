# Changelog

All notable changes to the MAKER Framework plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2025-12-22

### Fixed

- **Critical**: Fixed QA MCP tools not being triggered during maker-reviewer Check 8
  - Root cause: Tool names in agent definitions didn't match actual plugin tool names
  - Agent definitions used `mcp__claude-qa__*` but plugin provides `mcp__plugin_maker-framework_maker-qa__*`
  - Updated all tool references in `maker-reviewer.md` and `maker-decomposition-discriminator.md`

### Changed

- **QA MCP detection method**: Changed from file-based (`.mcp.json` lookup) to ping-based detection
  - Reviewer now calls `mcp__plugin_maker-framework_maker-qa__ping` to verify server availability
  - More reliable detection that works in both plugin and standalone modes
  - Added `ping` tool to maker-reviewer's tool list

### Updated

- `agents/maker-reviewer.md`: Updated all QA tool references to use plugin-qualified names
- `agents/maker-decomposition-discriminator.md`: Updated `check_prd_alignment` tool reference
- `docs/QA-MCP-INTEGRATION.md`: Added "Tool Names (Plugin Context)" section, distinguished plugin vs standalone modes
- `docs/TROUBLESHOOTING.md`: Split QA troubleshooting into plugin mode and standalone mode solutions

## [1.1.1] - 2025-12-22

### Added

- **Frontend Architect System**: Integrated Senior Frontend Architect + Avant-Garde UI Designer persona into CLAUDE.md
  - Default operating mode with execution focus and clarification rules
  - ULTRATHINK protocol for deep multi-lens analysis (UX, technical, accessibility, scalability)
  - Design philosophy: intentional minimalism, purpose-driven elements
  - Frontend implementation standards (library discipline, stack preferences, WCAG 2.2 AA)
  - Response format guidelines for normal and ULTRATHINK modes

## [1.1.0] - 2025-12-22

### Changed

- **Fixed broken import**: Removed non-portable `@../maker-framework/CLAUDE.md` import
- Root CLAUDE.md now contains critical rules directly (always loaded)

### Added

- **Lazy-loaded CLAUDE.md files** for better context management:
  - `skills/maker-orchestrator/CLAUDE.md` - Detailed orchestration (loaded when skill activates)
  - `agents/CLAUDE.md` - Agent coordination rules (loaded when working with agents)
- Uses Claude Code lazy loading: subdirectory CLAUDE.md files only load when those directories are accessed

## [1.0.9] - 2025-12-22

### Added

- **Plugin CLAUDE.md with import**: Created CLAUDE.md that imports main framework orchestration via `@../maker-framework/CLAUDE.md`
  - Enables automatic sync between plugin and framework instructions
  - Leverages Claude Code lazy loading for cleaner architecture
  - Eliminates need to maintain duplicate orchestration logic

### Changed

- Updated SKILL.md with fully qualified subagent_type names (`maker-framework:maker-*`)
- Updated commands/maker.md with fully qualified subagent_type names
- All agent invocations now use `maker-framework:maker-solver` format instead of `maker-solver`

## [1.0.8] - 2025-12-22

### Fixed

- **Critical**: Fixed orchestrator bypassing maker-solver and executing steps directly
  - Main thread was calling Write/Edit/Bash tools directly instead of delegating to maker-solver
  - Added explicit "CRITICAL: Solver Delegation Requirement" enforcement section
  - Clear WRONG vs CORRECT examples showing proper Task tool usage

### Changed

- Updated all `subagent_type` references to use fully qualified names:
  - `maker-solver` -> `maker-framework:maker-solver`
  - `maker-decomposition` -> `maker-framework:maker-decomposition`
  - `maker-red-flag` -> `maker-framework:maker-red-flag`
  - `maker-reviewer` -> `maker-framework:maker-reviewer`
  - And all other agents
- Added enforcement language: "If you find yourself about to use Write, Edit, or Bash directly during step execution - STOP"
- Section 3a now explicitly states: "MANDATORY: You MUST use the Task tool here"

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
