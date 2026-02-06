---
name: fetching-dbt-docs
description: Use when fetching dbt documentation, looking up dbt features, or answering questions about dbt Cloud, dbt Core, or the dbt Semantic Layer
user-invocable: false
metadata:
  author: dbt-labs
---

# Fetch dbt Docs

## Overview

dbt docs have LLM-friendly URLs. Always append `.md` to get clean markdown instead of HTML.

## URL Pattern

| Browser URL | LLM-friendly URL |
|-------------|------------------|
| `https://docs.getdbt.com/docs/dbt-cloud-apis/service-tokens` | `https://docs.getdbt.com/docs/dbt-cloud-apis/service-tokens.md` |
| `https://docs.getdbt.com/reference/commands/run` | `https://docs.getdbt.com/reference/commands/run.md` |

## Quick Reference

| Resource | URL | Use Case |
|----------|-----|----------|
| Single page | Add `.md` to any docs URL | Fetch specific documentation |
| Page index | `https://docs.getdbt.com/llms.txt` | Find all available pages |
| Full docs | `https://docs.getdbt.com/llms-full.txt` | Search across all docs (filter by keyword first) |

## Fetching a Single Page

```
WebFetch: https://docs.getdbt.com/docs/path/to/page.md
```

Always add `.md` to the URL path.

## Finding Pages

### Step 1: Search the Index First

Use `llms.txt` to search page titles and descriptions:

```
WebFetch: https://docs.getdbt.com/llms.txt
Prompt: "Find pages related to [topic]. Return the URLs."
```

This is fast and usually sufficient.

### Step 2: Search Full Docs (Only if Needed)

If the index doesn't have results, use the script to search full page content:

The search script is located at `scripts/search-dbt-docs.sh` relative to this skill's base directory.

```bash
<SKILL_BASE_DIR>/scripts/search-dbt-docs.sh <keyword>

# Examples
<SKILL_BASE_DIR>/scripts/search-dbt-docs.sh semantic_model
<SKILL_BASE_DIR>/scripts/search-dbt-docs.sh "incremental strategy"
<SKILL_BASE_DIR>/scripts/search-dbt-docs.sh metric dimension  # OR search

# Force fresh download (bypass 24h cache)
<SKILL_BASE_DIR>/scripts/search-dbt-docs.sh metric --fresh
```

**Important:** Replace `<SKILL_BASE_DIR>` with the actual base directory path provided when this skill is loaded.


Then fetch individual pages with `.md` URLs.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Fetching HTML URL without `.md` | Always append `.md` to docs URLs |
| Searching llms-full.txt first | Search llms.txt index first, only use full docs if no results |
| Loading llms-full.txt entirely | Use the search script to filter, then fetch individual pages |
| Guessing page paths | Use llms.txt index to find correct paths |
