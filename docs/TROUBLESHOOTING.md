# MAKER Framework Troubleshooting Guide

This guide helps resolve common issues with the MAKER framework.

## Common Issues

### MAKER Not Activating

**Symptoms:**
- Simple responses instead of MAKER workflow
- No `[MAKER] Decomposing task...` message

**Causes & Solutions:**

1. **CLAUDE.md not in correct location**
   ```bash
   # Check if file exists
   ls ~/.claude/CLAUDE.md

   # If missing, copy it
   cp /path/to/maker-framework/CLAUDE.md ~/.claude/CLAUDE.md
   ```

2. **Request doesn't contain trigger words**

   MAKER activates on: `create`, `build`, `implement`, `add`, `develop`, `make`, `set up`, `configure`, `refactor`, `migrate`

   Force MAKER with:
   ```
   use MAKER: update the configuration file
   ```

3. **User explicitly opted out**

   Words like `quick`, `simple`, `no MAKER` skip MAKER. Remove these if you want MAKER.

---

### Subagent Not Found

**Symptoms:**
- Error: "Unknown agent type: maker-decomposition"
- Partial MAKER execution

**Solutions:**

1. **Check subagent files exist**
   ```bash
   ls ~/.claude/agents/maker/
   ```

   Should show 10 files:
   - maker-decomposition.md
   - maker-decomposition-discriminator.md
   - maker-solver.md
   - maker-red-flag.md
   - maker-solution-discriminator.md
   - maker-reviewer.md
   - maker-parallel-coordinator.md
   - maker-complexity-estimator.md
   - maker-cache-manager.md
   - maker-checkpoint-manager.md

2. **Re-copy subagent files**
   ```bash
   cp /path/to/maker-framework/subagents/*.md ~/.claude/agents/maker/
   ```

3. **Check file permissions**
   ```bash
   chmod 644 ~/.claude/agents/maker/*.md
   ```

---

### Decomposition Rejected

**Symptoms:**
- Message: "REJECTED - Decomposition fundamentally flawed"
- MAKER stops early

**Causes & Solutions:**

1. **Task too vague**

   Bad: "Make it better"
   Good: "Add input validation to the login form"

2. **Conflicting requirements**

   Clarify your request to remove contradictions.

3. **Impossible constraints**

   Ensure all requirements are achievable.

---

### Step Keeps Failing (BLOCKED)

**Symptoms:**
- Same step fails multiple times
- Message: "STATUS: BLOCKED" repeatedly

**Solutions:**

1. **Check previous step succeeded**

   A step may depend on output that doesn't exist.

2. **Verify file/directory exists**
   ```bash
   ls -la /path/to/expected/file
   ```

3. **Check permissions**
   ```bash
   # For read access
   cat /path/to/file

   # For write access
   touch /path/to/directory/test.txt
   ```

4. **Review the blocker details**

   The BLOCKED output explains the specific issue.

---

### Pipeline Stuck in Review Loop

**Symptoms:**
- Same issues keep appearing after fixes
- Loop counter reaches 3

**Causes & Solutions:**

1. **Issues not actually fixed**

   Review the fix attempts to ensure they addressed the root cause.

2. **New issues introduced by fixes**

   Each fix may create new problems. Simplify the approach.

3. **Reviewer too strict**

   Some issues may be subjective. Consider if they truly need fixing.

**Manual intervention:**
```
skip MAKER: just apply this specific change...
```

---

### Red-Flag Validation Failures

**Symptoms:**
- "FLAGGED" results repeatedly
- Outputs rejected for being too long

**Solutions:**

1. **Simplify the step**

   If a step consistently produces long outputs, it may not be atomic enough.

2. **Check for confusing context**

   Unclear input state can cause rambling outputs.

3. **Request re-decomposition**
   ```
   The previous decomposition had steps that were too complex.
   Please re-decompose with simpler, more atomic steps.
   ```

---

### Voting Not Selecting Best Candidate

**Symptoms:**
- Selected solution seems suboptimal
- Lower-quality output chosen

**Solutions:**

1. **Check scoring breakdown**

   Review the detailed scores to understand selection.

2. **All candidates may be flawed**

   If all 3 candidates score poorly, the step may need redesign.

3. **Report as issue**

   If voting consistently makes poor choices, file a bug report.

---

## Error Messages Reference

| Error Message | Meaning | Solution |
|--------------|---------|----------|
| "NEEDS_REVISION" | Decomposition needs adjustment | Automatic - MAKER will retry |
| "REJECTED" | Fundamental decomposition flaw | Simplify or clarify your request |
| "BLOCKED" | Step cannot proceed | Check dependencies and permissions |
| "FLAGGED" | Solver output unreliable | Automatic resample |
| "NEEDS_FIXES" | Review found issues | Automatic fix loop |
| "NO_VALID_CANDIDATES" | All voting candidates failed | Re-attempt the step |

---

## Performance Issues

### MAKER Too Slow

**Causes:**
- Too many steps in decomposition
- Too many critical steps requiring voting
- Multiple review cycles

**Solutions:**

1. **Simplify task scope**

   Break large tasks into smaller ones.

2. **Reduce critical step count**

   Only security/database/API steps truly need voting.

3. **Accept "good enough"**

   Some review issues may be minor. Consider overriding:
   ```
   skip MAKER: this is good enough, just finish it
   ```

### High API Costs

**Causes:**
- Voting multiplies API calls by 3x
- Review loops add overhead

**Solutions:**

1. **Use for complex tasks only**
   ```
   quick: simple one-line fix
   ```

2. **Reduce decomposition granularity**

   Slightly larger steps = fewer API calls

---

## Getting Help

If these solutions don't resolve your issue:

1. **Check GitHub Issues**: Someone may have encountered the same problem
2. **File a New Issue**: Include:
   - Your MAKER configuration
   - The failing task
   - Error messages
   - Steps to reproduce

3. **Include Logs**: Set verbose mode and capture output

---

## Debug Mode

For detailed debugging, add to your request:

```
[DEBUG MODE]
Create a function that...
```

This will show full agent outputs instead of just progress messages.

---

## QA MCP Integration Issues

### Check 8 Always Skipped

**Symptoms:**
- Check 8 reports "SKIPPED - QA MCP not configured"
- QA tools never execute

**Solutions:**

1. **Verify .mcp.json exists**
   ```bash
   cat .mcp.json
   ```
   Should contain `claude-qa` server configuration.

2. **Verify claude-qa server is configured**
   ```json
   {
     "mcpServers": {
       "claude-qa": {
         "type": "stdio",
         "command": "python",
         "args": ["-m", "qa_server"]
       }
     }
   }
   ```

3. **Install QA engine package**
   ```bash
   pip install claude-qa-engine-mcp
   python -m qa_server --help
   ```

4. **Restart Claude Code** to reload MCP configuration

---

### QA Tools Return Errors

**Symptoms:**
- Check 8 reports "FAIL" with error messages
- Tool invocations fail

**Solutions:**

1. **Check Python environment**
   ```bash
   which python
   python --version  # Should be 3.9+
   ```

2. **Verify qa_server module**
   ```bash
   python -c "import qa_server; print('OK')"
   ```

3. **Check environment variables**
   ```bash
   echo $QA_CONFIG_PATH
   echo $QA_REPORTS_DIR
   ```

4. **Test MCP server manually**
   ```bash
   python -m qa_server --help
   ```

---

### Tests Pass Locally but Fail in QA MCP

**Symptoms:**
- `pytest` works directly
- `mcp__claude-qa__run_tests` reports failures

**Solutions:**

1. **Check working directory**
   
   QA MCP may run from different directory. Use absolute paths in test configuration.

2. **Check environment isolation**
   
   MCP server may have different environment variables. Verify in qa-config.yaml.

3. **Check test discovery patterns**
   
   Ensure qa-config.yaml test patterns match your project structure.

---

### Coverage Reports 0% or N/A

**Symptoms:**
- get_coverage returns 0% or empty
- Coverage data not collected

**Solutions:**

1. **Install coverage tool**
   ```bash
   pip install coverage  # Python
   npm install -g nyc    # JavaScript
   ```

2. **Configure coverage in qa-config.yaml**
   ```yaml
   coverage:
     enabled: true
     source_dirs:
       - src/
     omit:
       - tests/
   ```

3. **Run coverage manually to verify**
   ```bash
   coverage run -m pytest
   coverage report
   ```

---

### Regressions Check Fails

**Symptoms:**
- check_regressions returns error
- "No baseline found" message

**Solutions:**

1. **Create baseline first**
   
   Run tests on main/master branch to establish baseline:
   ```bash
   git checkout main
   python -m qa_server create-baseline
   ```

2. **Verify baseline file exists**
   ```bash
   ls qa-reports/baseline.json
   ```

3. **Skip regression check if no baseline**
   
   This is expected on first run. Baseline will be created after first successful test run.

---

### MCP Server Timeout

**Symptoms:**
- QA tools hang then fail
- "Timeout" errors in Check 8

**Solutions:**

1. **Reduce test scope**
   
   Run subset of tests if full suite is slow:
   ```yaml
   # qa-config.yaml
   test_patterns:
     - tests/unit/**  # Skip slow integration tests
   ```

2. **Increase timeout** (if supported)
   ```yaml
   # qa-config.yaml
   timeout: 120  # seconds
   ```

3. **Check for infinite loops** in tests

4. **Run tests outside MCP** to measure actual runtime

