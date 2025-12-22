# Decomposition Pattern Cache Schema

## Overview

This cache stores reusable decomposition patterns for the MAKER framework. Patterns are categorized by task type and can be retrieved to accelerate future decompositions.

## Index Structure (index.json)

```json
{
  "version": "1.0.0",
  "created_at": "ISO-8601 timestamp",
  "last_updated": "ISO-8601 timestamp",
  "patterns_by_type": {
    "CRUD": [],
    "REFACTOR": [],
    "ADD_FEATURE": [],
    "MIGRATE": [],
    "FIX": [],
    "CONFIG": [],
    "TEST": [],
    "OTHER": []
  }
}
```

## Pattern Entry Structure

Each entry in a category array:

```json
{
  "id": "unique-pattern-id",
  "name": "Human-readable pattern name",
  "description": "What this pattern accomplishes",
  "created_at": "ISO-8601 timestamp",
  "usage_count": 0,
  "success_rate": 1.0,
  "file": "pattern-id.json"
}
```

## Pattern File Structure

Individual pattern files stored as `{pattern-id}.json`:

```json
{
  "id": "unique-pattern-id",
  "type": "CRUD | REFACTOR | ADD_FEATURE | MIGRATE | FIX | CONFIG | TEST | OTHER",
  "name": "Pattern name",
  "description": "Detailed description",
  "keywords": ["keyword1", "keyword2"],
  "steps": [
    {
      "step_number": 1,
      "name": "Step name",
      "action": "Action description",
      "input_template": "Expected input state template",
      "output_template": "Expected output state template",
      "critical": false
    }
  ],
  "metadata": {
    "created_at": "ISO-8601 timestamp",
    "last_used": "ISO-8601 timestamp",
    "usage_count": 0,
    "success_count": 0,
    "failure_count": 0
  }
}
```

## Task Types

| Type | Description |
|------|-------------|
| CRUD | Create, Read, Update, Delete operations |
| REFACTOR | Code restructuring without behavior change |
| ADD_FEATURE | New functionality addition |
| MIGRATE | Moving or upgrading code/dependencies |
| FIX | Bug fixes and corrections |
| CONFIG | Configuration and setup tasks |
| TEST | Test creation and modification |
| OTHER | Tasks not fitting other categories |
