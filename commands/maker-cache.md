---
description: Manage MAKER pattern cache - list, clear, or inspect cached decompositions
allowed-tools: Read, Write, Bash, Glob
argument-hint: list | clear | inspect <pattern-id>
---

# MAKER Cache Command

Manage the decomposition pattern cache.

## Subcommands

Based on $ARGUMENTS:

### list

Show all cached decomposition patterns with usage statistics.

```
==========================================
         MAKER CACHE - LIST
==========================================

Total Patterns: {count}
Cache Directory: cache/decomposition-patterns/

------------------------------------------
PATTERNS BY TYPE
------------------------------------------

CRUD ({count}):
  - crud-api-endpoint (used {N} times, {success_rate}% success)
  - crud-form-component (used {N} times, {success_rate}% success)

ADD_FEATURE ({count}):
  - feature-auth-jwt (used {N} times, {success_rate}% success)

REFACTOR ({count}):
  - refactor-extract-function (used {N} times, {success_rate}% success)

{...other types...}

------------------------------------------
CACHE STATISTICS
------------------------------------------
Total Hits: {count}
Total Misses: {count}
Hit Rate: {percentage}%
Last Updated: {timestamp}

==========================================
```

### clear

Clear the pattern cache (with confirmation).

```
==========================================
         MAKER CACHE - CLEAR
==========================================

WARNING: This will remove all cached decomposition patterns.

Patterns to remove: {count}
Cache size: {size}

Clearing cache...
Removed {count} patterns.

Cache cleared successfully.

==========================================
```

### inspect <pattern-id>

Show details of a specific cached pattern.

```
==========================================
         MAKER CACHE - INSPECT
==========================================

Pattern ID: {pattern-id}

------------------------------------------
METADATA
------------------------------------------
Created: {timestamp}
Last Used: {timestamp}
Use Count: {count}
Success Rate: {percentage}%
Failure Count: {count}

------------------------------------------
SIGNATURE
------------------------------------------
Task Type: {type}
Complexity: {level}
Keywords: {list}
File Patterns: {list}

------------------------------------------
DECOMPOSITION
------------------------------------------
Total Steps: {N}

[001] {step name}
  Action: {action}

[002] {step name}
  Action: {action}

{...continue for all steps...}

------------------------------------------
EXECUTION HISTORY
------------------------------------------
- {timestamp}: SUCCESS (task-id-001)
- {timestamp}: SUCCESS (task-id-002)
- {timestamp}: FAILED (task-id-003) - {reason}

==========================================
```

## If Pattern Not Found

```
==========================================
         MAKER CACHE - INSPECT
==========================================

Pattern not found: {pattern-id}

Available patterns:
- {pattern-1}
- {pattern-2}
- {pattern-3}

Use /maker-framework:maker-cache list to see all patterns.

==========================================
```
