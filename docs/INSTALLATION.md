# MAKER Framework Installation Guide

This guide covers installation on all platforms supported by Claude Code.

## Prerequisites

### Required
- **Claude Code CLI**: The official CLI for Claude from Anthropic
- **Anthropic API Key**: Active API key with sufficient credits

### Recommended
- **Git**: For cloning the repository
- **A code editor**: For reviewing and customizing configuration

## Installation Methods

### Method 1: Global Installation (Recommended)

This makes MAKER available across all your projects.

#### Step 1: Clone the Repository

```bash
# Using HTTPS (replace <owner> with actual repository owner)
git clone https://github.com/<owner>/maker-framework.git

# Or using SSH
git clone git@github.com:<owner>/maker-framework.git

cd maker-framework
```

#### Step 2: Create Claude Directories

**macOS / Linux:**
```bash
mkdir -p ~/.claude/agents/maker
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\agents\maker"
```

**Windows (Git Bash):**
```bash
mkdir -p ~/.claude/agents/maker
```

#### Step 3: Copy Configuration Files

**macOS / Linux:**
```bash
# Copy main configuration
cp CLAUDE.md ~/.claude/CLAUDE.md

# Copy all subagent definitions
cp subagents/*.md ~/.claude/agents/maker/
```

**Windows (PowerShell):**
```powershell
# Copy main configuration
Copy-Item CLAUDE.md "$env:USERPROFILE\.claude\CLAUDE.md"

# Copy all subagent definitions
Copy-Item subagents\*.md "$env:USERPROFILE\.claude\agents\maker\"
```

#### Step 4: Verify Installation

```bash
# Check files are in place
ls ~/.claude/CLAUDE.md
ls ~/.claude/agents/maker/

# Should see:
# maker-decomposition.md
# maker-decomposition-discriminator.md
# maker-solver.md
# maker-red-flag.md
# maker-solution-discriminator.md
# maker-reviewer.md
```

### Method 2: Project-Specific Installation

Use this if you want MAKER for a specific project only.

#### Step 1: Navigate to Your Project

```bash
cd /path/to/your/project
```

#### Step 2: Copy Files

```bash
# Copy main configuration to project root
cp /path/to/maker-framework/CLAUDE.md ./CLAUDE.md

# Create agents directory in project
mkdir -p agents/maker

# Copy subagent definitions
cp /path/to/maker-framework/subagents/*.md agents/maker/
```

### Method 3: Manual Download (No Git)

If you don't have Git installed:

1. Download the repository as a ZIP from GitHub
2. Extract the ZIP file
3. Follow either Method 1 or Method 2 above

## Platform-Specific Notes

### macOS

No special configuration needed. The `~/.claude` directory is in your home folder.

### Linux

Same as macOS. Ensure you have write permissions to `~/.claude`.

### Windows

- Use PowerShell or Git Bash for the commands above
- The `~/.claude` directory maps to `C:\Users\<your-username>\.claude`
- File paths use backslashes in PowerShell, forward slashes in Git Bash

## Verifying MAKER is Working

After installation, test MAKER with a simple request:

```bash
claude-code
```

Then try:
```
Create a hello world function in Python
```

You should see:
```
[MAKER] Decomposing task...
[MAKER] 2 steps identified, validating...
[MAKER] Approved. Executing step 1/2...
...
```

## Updating MAKER

To update to the latest version:

```bash
cd /path/to/maker-framework
git pull origin main

# Re-copy files
cp CLAUDE.md ~/.claude/CLAUDE.md
cp subagents/*.md ~/.claude/agents/maker/
```

## Uninstalling MAKER

To remove MAKER:

```bash
# Remove configuration
rm ~/.claude/CLAUDE.md

# Remove subagents
rm -rf ~/.claude/agents/maker/
```

Or for project-specific:
```bash
rm ./CLAUDE.md
rm -rf ./agents/maker/
```

## Troubleshooting Installation

### "CLAUDE.md not found"

Ensure the file is in the correct location:
- Global: `~/.claude/CLAUDE.md`
- Project: `./CLAUDE.md` (in project root)

### "Subagent not found: maker-decomposition"

Check subagent files are present:
```bash
ls ~/.claude/agents/maker/
```

If empty, re-copy the files from the `subagents/` directory.

### "Permission denied"

Ensure you have write access:
```bash
chmod -R u+w ~/.claude/
```

### Windows Path Issues

Use forward slashes or escaped backslashes:
```powershell
# Correct
"$env:USERPROFILE\.claude\CLAUDE.md"

# Also correct
"~/.claude/CLAUDE.md"  # In Git Bash
```

## Next Steps

After installation:
1. Read the [README.md](../README.md) for usage examples
2. Try the [simple-task.md](../examples/simple-task.md) example
3. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues
