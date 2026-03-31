# Gap Detection Queries

This reference provides queries for finding documentation gaps in a dbt project. Each query has two versions: a **dbt-index SQL** query (preferred) and a **manifest.json jq fallback**.

> **Note:** dbt-index table names referenced here (`models`, `columns`, `tests`, `exposures`, `sources`) are from the dbt-index relational schema. The exact schema is under active development — column names may change before GA.

## Models Without Descriptions

### P0: Public models without descriptions

These are API contracts. Consumers depend on them.

**dbt-index:**
```sql
SELECT m.unique_id, m.name, m.schema_name, m.access, m.path
FROM models m
WHERE m.access = 'public'
  AND (m.description IS NULL OR m.description = '')
ORDER BY m.name
```

**manifest.json fallback:**
```bash
jq '[.nodes | to_entries[]
  | select(.value.resource_type == "model"
    and .value.access == "public"
    and (.value.description == null or .value.description == ""))
  | {name: .value.name, schema: .value.schema, path: .value.path}]' target/manifest.json
```

### P0: Models upstream of exposures without descriptions

These directly impact stakeholder-facing outputs.

**dbt-index:**
```sql
SELECT DISTINCT m.unique_id, m.name, m.path
FROM models m
JOIN model_dependencies md ON m.unique_id = md.upstream_id
JOIN exposures e ON md.downstream_id = e.unique_id
WHERE (m.description IS NULL OR m.description = '')
ORDER BY m.name
```

**manifest.json fallback:**
```bash
# First, get all models referenced by exposures
jq '
  [.exposures | to_entries[] | .value.depends_on.nodes[]] as $exposure_deps |
  [.nodes | to_entries[]
    | select(.key as $k | $exposure_deps | index($k))
    | select(.value.description == null or .value.description == "")
    | {name: .value.name, path: .value.path}]
' target/manifest.json
```

### P2: All models without descriptions (by access level)

**dbt-index:**
```sql
SELECT m.access, count(*) AS undescribed_count, count(*) * 100.0 / (
  SELECT count(*) FROM models m2 WHERE m2.access = m.access
) AS pct_undescribed
FROM models m
WHERE (m.description IS NULL OR m.description = '')
GROUP BY m.access
ORDER BY
  CASE m.access
    WHEN 'public' THEN 1
    WHEN 'protected' THEN 2
    WHEN 'private' THEN 3
    ELSE 4
  END
```

**manifest.json fallback:**
```bash
jq '[.nodes | to_entries[]
  | select(.value.resource_type == "model"
    and (.value.description == null or .value.description == ""))
  | {name: .value.name, access: (.value.access // "private"), path: .value.path}]
  | group_by(.access)
  | map({access: .[0].access, count: length, models: [.[].name]})' target/manifest.json
```

## Columns Without Descriptions

### P1: Columns used in joins without descriptions

Ambiguous join keys cause silent data corruption (e.g., the account_id problem where 136 records share value '1').

**dbt-index:**
```sql
SELECT c.model_name, c.name AS column_name, c.data_type
FROM columns c
WHERE (c.description IS NULL OR c.description = '')
  AND (c.name LIKE '%_id' OR c.name LIKE '%_key' OR c.name LIKE '%_fk')
ORDER BY c.model_name, c.name
```

**manifest.json fallback:**
```bash
jq '[.nodes | to_entries[]
  | select(.value.resource_type == "model")
  | .value as $model
  | ($model.columns // {} | to_entries[])
  | select((.value.description == null or .value.description == "")
    and (.key | test("_id$|_key$|_fk$")))
  | {model: $model.name, column: .key, path: $model.path}]' target/manifest.json
```

### P3: Columns appearing in multiple models with different or missing descriptions

**dbt-index:**
```sql
SELECT c.name AS column_name,
       count(DISTINCT c.model_name) AS model_count,
       count(DISTINCT c.description) AS distinct_descriptions,
       array_agg(DISTINCT c.model_name) AS models
FROM columns c
WHERE c.name IN (
  SELECT name FROM columns GROUP BY name HAVING count(DISTINCT model_name) > 1
)
GROUP BY c.name
HAVING count(DISTINCT c.description) > 1
   OR count(CASE WHEN c.description IS NULL OR c.description = '' THEN 1 END) > 0
ORDER BY model_count DESC
```

## Models Without Tests

### P2: Models with no tests at all

Untested models are undocumented assumptions.

**dbt-index:**
```sql
SELECT m.unique_id, m.name, m.access, m.path
FROM models m
WHERE m.unique_id NOT IN (
  SELECT DISTINCT t.attached_node
  FROM tests t
  WHERE t.attached_node IS NOT NULL
)
ORDER BY
  CASE m.access
    WHEN 'public' THEN 1
    WHEN 'protected' THEN 2
    ELSE 3
  END,
  m.name
```

**manifest.json fallback:**
```bash
jq '
  [.nodes | to_entries[] | select(.value.resource_type == "test") | .value.depends_on.nodes[]] | unique as $tested |
  [.nodes | to_entries[]
    | select(.value.resource_type == "model")
    | select(.key as $k | $tested | index($k) | not)
    | {name: .value.name, access: (.value.access // "private"), path: .value.path}]
' target/manifest.json
```

## Sources Without Descriptions

### P2: Sources with no description

Foundation layer context that helps understand where data comes from.

**dbt-index:**
```sql
SELECT s.source_name, s.name AS table_name, s.path
FROM sources s
WHERE (s.description IS NULL OR s.description = '')
ORDER BY s.source_name, s.name
```

**manifest.json fallback:**
```bash
jq '[.sources | to_entries[]
  | select(.value.description == null or .value.description == "")
  | {source: .value.source_name, table: .value.name, path: .value.path}]' target/manifest.json
```

## Summary Report Query

Use this to produce a high-level gap report to show the user before starting the interview.

**dbt-index:**
```sql
SELECT
  'Models without descriptions' AS gap_type,
  count(*) AS count
FROM models WHERE (description IS NULL OR description = '')
UNION ALL
SELECT
  'Public models without descriptions',
  count(*)
FROM models WHERE access = 'public' AND (description IS NULL OR description = '')
UNION ALL
SELECT
  'ID/key columns without descriptions',
  count(*)
FROM columns
WHERE (description IS NULL OR description = '')
  AND (name LIKE '%_id' OR name LIKE '%_key')
UNION ALL
SELECT
  'Models with no tests',
  count(*)
FROM models
WHERE unique_id NOT IN (
  SELECT DISTINCT attached_node FROM tests WHERE attached_node IS NOT NULL
)
UNION ALL
SELECT
  'Sources without descriptions',
  count(*)
FROM sources WHERE (description IS NULL OR description = '')
ORDER BY count DESC
```

## YAML File Scanning Fallback (no manifest)

When neither dbt-index nor manifest.json is available, scan YAML files directly:

```
# Find all properties files
Glob: models/**/*.yml

# In each file, look for models missing descriptions
# Read the file and check for model entries where description is absent or empty
```

This is the most limited analysis — you can only detect missing descriptions. You cannot analyze lineage, test coverage, column usage patterns, or access levels. Recommend the user compile their project (`dbt compile` or `fusion compile`) to produce a manifest for better analysis.
