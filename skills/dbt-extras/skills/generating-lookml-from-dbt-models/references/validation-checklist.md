# LookML Validation Checklist

Adversarial self-test checklist for generated LookML. Run after Step 9 (`uvx lkml`). Fix all failures before declaring done.

---

## How to Run

### Syntax validation (Step 9)

```bash
for f in *.view.lkml *.explore.lkml *.model.lkml; do
  uvx lkml "$f" > /dev/null && echo "✅ $f" || echo "❌ SYNTAX ERROR: $f"
done
```

`uvx lkml` is a real LookML parser. Exit 0 = valid, non-zero = syntax error. Fix syntax errors first.

### Parse to JSON for structural checks (Step 10)

```bash
uvx lkml --format=json myfile.view.lkml > myfile.json
```

Use the JSON to run the structural checks below programmatically, or check manually.

---

## Critical Checks (will break Looker if failed)

### C1 — No `${TABLE}.1` in measure SQL

**Check:** Search all `.view.lkml` files for the string `${TABLE}.1`.

```bash
grep -r "\${TABLE}\.[0-9]" *.view.lkml && echo "❌ FAIL" || echo "✅ PASS"
```

**Why:** `SUM(1)` → `sql: 1 ;;` not `sql: ${TABLE}.1 ;;`. The `.1` is not a column.

---

### C2 — No `dimension_group` name with grain suffix

**Check:** Search for `dimension_group:` blocks whose name ends in `_date`, `_week`, `_month`, `_quarter`, `_year`.

```bash
grep -E "dimension_group:\s+\w+_(date|week|month|quarter|year)\s*\{" *.view.lkml && echo "❌ FAIL" || echo "✅ PASS"
```

**Why:** Looker appends the grain suffix automatically. A group named `ordered_at_date` produces `ordered_at_date_date` — duplicated grain.

---

### C3 — Every `join:` view exists as a `.view.lkml` file

**Check:** Extract all `join: view_name {` from explore files. Verify `{view_name}.view.lkml` exists.

**Why:** An explore that references a non-existent view will fail to load in Looker.

---

### C4 — Every `explore_source:` name is an existing `explore:`

**Check:** Extract all `explore_source: explore_name {` from view files. Verify `explore: explore_name {` exists in an explore file.

**Why:** A native derived table that targets a non-existent explore cannot be materialized.

---

### C5 — Every ratio measure SQL contains `NULLIF`

**Check:** Find all `type: number` measures where `sql:` contains `/`. Verify each contains `NULLIF`.

```bash
# Pseudocode: for each measure with type: number and "/" in sql, check for NULLIF
```

**Why:** Division-by-zero silently returns `NULL` in some warehouses and errors in others. `NULLIF` is non-negotiable for ratio measures.

---

### C6 — All `sql_on:` values use `${view.column}` format

**Check:** Search for `sql_on:` values that contain raw column names (no `${...}` wrapper).

```bash
grep "sql_on:" *.explore.lkml | grep -v "\${" && echo "❌ Raw col refs found" || echo "✅ PASS"
```

**Why:** Raw column references in `sql_on` bypass Looker's field resolver and break with PDTs.

---

### C7 — No duplicate measure names within a view

**Check:** For each view file, collect all `measure: name {` entries. Assert no name appears twice.

**Why:** Duplicate measure names cause a parse error in Looker.

---

### C8 — Multi-line descriptions collapsed

**Check:** Search for `description:` values containing literal newlines.

**Why:** LookML `description:` must be a single-line string. Multi-line values cause parse errors.

---

### C9 — `label:` present where source metric had `label:`

**Check:** For each metric that had a `label:` field in the source dbt YAML, verify the generated measure has `label:`.

**Why:** Without `label:`, Looker derives a label from the field name, which may not match the user's intended display name.

---

### C10 — Untranslatable metrics skipped with comment

**Check:** For every `type: derived`, `type: conversion`, or `type: cumulative` metric in the source YAML, verify there is NO measure in the output — only the warning comment block.

**Why:** Emitting broken SQL for MetricFlow-only metrics will fail at query time in Looker with cryptic errors.

---

### C11 — Databricks: `datatype: timestamp` on all `dimension_group` blocks

**Check (Databricks only):** Verify every `dimension_group { type: time }` block includes `datatype: timestamp`.

**Why:** Databricks uses `TIMESTAMP_NTZ` by default. Without explicit `datatype`, Looker may infer the wrong type and produce incorrect date truncations.

---

## Structural Completeness Checks

### S1 — Model file exists

**Check:** `{project_name}.model.lkml` exists and contains `connection:` and at least one `include:`.

**Why:** Without a model file, Looker cannot load any views or explores.

---

### S2 — All target views are included in the explore

**Check:** If the user specified N models, verify there are N `.view.lkml` files (plus saved_query views if applicable).

---

### S3 — Explore file exists

**Check:** `explores.explore.lkml` (or similar) exists and has at least one `explore:` block.

---

## Validation Limitations

This checklist validates **syntax and structural consistency** only.

| Validation type | Tool | Status |
|----------------|------|--------|
| LookML syntax | `uvx lkml` | ✅ Available |
| Cross-reference (join views exist) | Checklist above | ✅ Manual/script |
| SQL dialect correctness | — | ❌ None available offline |
| Field references against real warehouse columns | Spectacles or Looker API | ❌ Requires live connection |

State this limitation explicitly in the output summary:
> "Syntax and structural validation passed. SQL correctness against warehouse columns requires a live Looker connection."
