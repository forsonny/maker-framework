# Changelog

All notable changes to the MAKER Framework plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
