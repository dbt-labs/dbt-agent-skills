# Classification Categories

Detailed definitions for the 4-category triage framework used to classify dbt-core to dbt v2 migration errors.

## Contents
- [Category A: Auto-Fixable (Safe)](#category-a-auto-fixable-safe)
- [Category B: Guided Fixes (Need Approval)](#category-b-guided-fixes-need-approval)
- [Category C: Needs Your Input](#category-c-needs-your-input)
- [Category D: Blocked (Not Fixable in Project)](#category-d-blocked-not-fixable-in-project)
- [Verifying Against the Real Warehouse Before Classifying as Category D](#verifying-against-the-real-warehouse-before-classifying-as-category-d)

## Category A: Auto-Fixable (Safe)

**Can fix automatically with HIGH confidence.**

These are low-risk changes where the fix is deterministic and well-understood. No user approval needed beyond initial confirmation.

### Sub-patterns

| Sub-pattern | Error Code | Signal | Fix | Risk |
|-------------|------------|--------|-----|------|
| Quote nesting in config | `dbt1000` | `syntax error: unexpected identifier` with nested quotes | Use single quotes outside: `warn_if='{{ "text" }}'` | LOW — syntactic only |

### When to use Category A
- The fix is a known, safe transformation
- There is exactly one correct fix (no ambiguity)
- The change has no semantic impact on the project

---

## Category B: Guided Fixes (Need Approval)

**Can fix with user approval — show diffs first.**

These fixes are well-understood but may change project behavior. Always show the exact diff and get approval before applying.

### Sub-patterns

| Sub-pattern | Error Code | Signal | Fix | Risk |
|-------------|------------|--------|-----|------|
| Config API deprecated | `dbt1501` | "Argument must be a string or a list. Received: (empty)" | `config.require('meta').key` to `config.meta_require('key')` | MEDIUM — API change |
| Plain dict `.meta_get()` error | `dbt1501` | "unknown method: map has no method named meta_get" | `dict.meta_get()` to `dict.get()` | LOW — method name only |
| Unused schema.yml entries | `dbt1005` | "Unused schema.yml entry for model 'ModelName'" | Remove orphaned YAML entry | LOW — just a warning |
| Source name mismatches | `dbt1005` | "Source 'Name' not found" | Align source references with YAML definitions | MEDIUM — v2 is strict on naming |
| Case-sensitive column identifier mismatch | `dbt0227` (UnresolvedIdentifier), or `dbt0209` (FunctionResolutionFailed) only when the signal below is present | "No column X found" or "Available are ..." listing the same name in a different case, naming a quoted/reserved column — other `FunctionResolutionFailed` causes (missing function, wrong overload/argument types) are a different problem, not this pattern | Quote the identifier with its real stored casing (verify via `INFORMATION_SCHEMA.COLUMNS`, not just the analyzer's cached schema), source-side only | MEDIUM — reserved words (`group`, `unique`, `option`, `interval`, `global`, `default`, `action`, `to`) must be quoted, and quoting makes them case-sensitive |
| Static analysis false positive on a PRODUCTION model | `dbt0227`, `dbt0209` (identifier/column-existence findings only — not other static analysis codes) | Error persists after [warehouse verification](#verifying-against-the-real-warehouse-before-classifying-as-category-d) confirms the analyzer's cached schema is stale, not the code | `static_analysis: off`, scoped per-model, with explicit user sign-off | HIGH if unverified (silences a real runtime failure) — safe only after verification |
| YAML syntax errors | `dbt1013` | "YAML mapping values not allowed" | Fix quotes, indentation, colons | MEDIUM — syntax dependent |
| Unexpected config keys | `dbt1060` | "Unexpected key in config" | Move custom keys to `meta:` section | MEDIUM — changes config structure |
| Package version issues | `dbt1005`, `dbt8999` | "Package not in lookup map", "Cannot combine non-exact versions" | Update versions, use exact pins | MEDIUM — may change package behavior |
| SQL parsing errors | — | SQL parsing failures under static analysis | Suggest rewriting the logic (with user approval), or set `static_analysis: off` for the model | MEDIUM — may change analysis behavior |
| "--models flag deprecated" | — | If the repro command uses `--models/-m`, replace with `--select/-s` | MEDIUM — may change command behavior |
| Duplicate doc blocks | `dbt1501` | "Duplicate doc block" | Rename or delete conflicting blocks | LOW — documentation only |
| Seed CSV format | `dbt1021` | "Seed cast error" | Clean CSV (ISO dates, lowercase `null`) | MEDIUM — data format change |
| Empty SELECT | `dbt0404` | "SELECT with no columns" | Add `SELECT 1` or actual column list | LOW — placeholder needed |

### When to use Category B
- The fix is well-understood but requires a judgment call
- Multiple files may be affected
- The change could affect query behavior or project structure
- The user should see exactly what will change before it's applied

### Fix procedure: case-sensitive column identifier mismatch

A common v2-strict-mode pattern when running the repro command with `--static-analysis strict`. Reserved words must be quoted to parse, but quoting also makes them case-sensitive — a common bug is quoting the word in its natural lowercase (`"default"`) when the real column is unquoted-created and therefore stored uppercase (`DEFAULT`). This pattern requires the "Available are ..." evidence in the Signal column above — a `dbt0209` FunctionResolutionFailed without that evidence is a different problem (e.g. missing function or wrong argument types) and should be triaged separately, not assumed to be a casing issue.

1. Confirm the real stored casing by querying `INFORMATION_SCHEMA.COLUMNS` (or your warehouse's equivalent — see [Verifying Against the Real Warehouse](#verifying-against-the-real-warehouse-before-classifying-as-category-d)) against the live warehouse. Do not substitute the error's own "Available are ..." list for this — that list is drawn from the same cached schema this check exists to catch, and can itself be stale. Use it only as a secondary comparison against the query result, never as a replacement for it.
2. Check the model's own `schema.yml` for a documented column name/casing contract before changing anything. If the column is documented (or has tests) under a specific output name, add an explicit alias so the fix corrects only the source-side reference, not the resulting column name.
3. Apply the corrected quoting/casing on the source side only.
4. Re-run the repro command scoped to that one node (`--select <model>`) before moving to the next file.

### Guardrail: suppressing static analysis on production models

This applies only to `dbt0227`/`dbt0209` identifier/column-existence findings that [warehouse verification](#verifying-against-the-real-warehouse-before-classifying-as-category-d) confirms are cache artifacts — not a general license to suppress other static analysis codes, which the column-existence check can't validate.

Never apply `static_analysis: off` to a production model without first completing that verification — it doesn't change what the warehouse resolves at runtime, so suppressing a real mismatch turns a compile-time error into a silent production failure.

- Scope per-model in `dbt_project.yml`, not directory-wide, unless every model in the directory is genuinely affected
- Get explicit sign-off per model or per confirmed-safe batch
- Flag any model suppressed WITHOUT verification as a follow-up — don't let it disappear from the classification summary

---

## Category C: Needs Your Input

**Requires user decision — multiple valid approaches.**

These errors have more than one correct resolution. The skill should present options and let the user decide.

### Sub-patterns

| Sub-pattern | Signal | Options |
|-------------|--------|---------|
| Permission errors — Hardcoded FQNs | Permission denied, access errors with `FROM database.schema.table` | (1) Replace with `{{ ref('table_name') }}` if dbt model, (2) Replace with `{{ source('schema', 'table_name') }}` if source, (3) Ensure credentials if external table |
| Failing `analyses/` queries | Errors in `analyses/` directory | (1) Disable static analysis, (2) Delete the file, (3) Fix the query |

### When to use Category C
- There are multiple valid fixes and the right one depends on project context
- The user has information the agent doesn't (e.g., "Is this a source or a model?")
- The decision involves tradeoffs the user should make

---

## Category D: Blocked (Not Fixable in Project)

**Requires v2 updates — NOT fixable in user code.**

These errors cannot be resolved by changing the user's project. They are caused by gaps in the v2 engine.

When an error is Category D, identify it as blocked, explain why, link the GitHub issue, and suggest alternative approaches while clearly describing the risks. Let the user decide whether to apply a workaround or wait for the v2 fix.

### Sub-patterns

| Sub-pattern | Signal | Message | Action |
|-------------|--------|---------|--------|
| v2 engine gaps | MiniJinja filter differences, parser gaps, missing implementations, wrong materialization dispatch | "This requires a v2 update (tracked in issue #XXXX)" | Search GitHub issues, link if found. Suggest alternatives with risk descriptions. |
| Known GitHub issues | Incremental models with `on_schema_change='sync_all_columns'`, unsupported macro patterns, adapter-specific gaps | "Known limitation — tracked in issue #XXXX" | Link issue, check if closed (suggest v2 upgrade). Suggest alternatives with risk descriptions. |
| Engine crashes | `panic!`, `internal error`, `RUST_BACKTRACE`, `not yet implemented` | "This is a v2 engine crash/missing implementation" | Document and report. Suggest alternatives if possible, with clear risk descriptions. |

### When to use Category D
- The error is caused by a v2 engine gap, not user code
- No direct fix exists in the user's project — the root cause requires a v2 update
- The error involves internal dispatch, materialization routing, or adapter methods
- Workarounds may exist but carry risks (fragility, breakage on future v2 updates) — suggest them with clear risk descriptions and let the user decide

### GitHub issue search
When you suspect a v2 bug:
1. Search: `site:github.com/dbt-labs/dbt-fusion/issues <error_code> <keywords>`
2. If open issue exists: Link it and explain status
3. If closed: Suggest updating v2 version
4. If no issue found: Document the error pattern for the user to report

---

## Verifying Against the Real Warehouse Before Classifying as Category D

Before concluding an `UnresolvedIdentifier`/`FunctionResolutionFailed` error is a real bug OR a v2 engine/cache gap, verify against the live warehouse. `INFORMATION_SCHEMA.COLUMNS` qualification differs by adapter — use the query matching your warehouse:

| Adapter | Query |
|---|---|
| Snowflake | `dbt show --inline "SELECT column_name FROM <database>.INFORMATION_SCHEMA.COLUMNS WHERE table_schema = '<SCHEMA>' AND table_name = '<TABLE>' ORDER BY ordinal_position"` |
| Postgres / Redshift | `dbt show --inline "SELECT column_name FROM information_schema.columns WHERE table_schema = '<schema>' AND table_name = '<table>' ORDER BY ordinal_position"` (no database qualifier — these only see the connected database) |
| BigQuery | `dbt show --inline "SELECT column_name FROM \`<project>.<dataset>.INFORMATION_SCHEMA.COLUMNS\` WHERE table_name = '<table>' ORDER BY ordinal_position"` (dataset-qualified; no `table_schema` filter needed) |
| Databricks | `dbt show --inline "SELECT column_name FROM <catalog>.information_schema.columns WHERE table_schema = '<schema>' AND table_name = '<table>' ORDER BY ordinal_position"` (catalog-qualified, Unity Catalog) |

If your adapter isn't listed, check its docs for the equivalent metadata view — the pattern (query column names for the actual table, compare to what the error claims) holds regardless of syntax.

This is metadata-only (column names/types), not row-level data, and safe to run freely.

- If the column exists with different real-world casing than the model references → real bug, fix the casing (see the [case-sensitive identifier fix procedure](#fix-procedure-case-sensitive-column-identifier-mismatch)).
- If the column exists exactly as referenced, matching the error's own "Available are ..." list → this is a static-analysis cache artifact, not a real bug. Try `dbt clean` + recompile first. If it still fails, or fails inconsistently between an isolated `--select` compile and a full-project compile with unchanged code, that inconsistency itself is the evidence — don't keep guessing at code changes to satisfy a non-deterministic checker.

Do not classify an error as Category D from the error message alone. The message's "Available are ..." column list can itself be stale — cross-check it against `INFORMATION_SCHEMA` before trusting it either way.
