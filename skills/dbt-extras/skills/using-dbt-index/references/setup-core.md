# Setup: dbt Core Path

Use this when the project runs dbt Core (not Fusion).

## Creating the index

dbt Core produces JSON artifacts in `target/`. These must be ingested into the index separately.

### Step 1 — Ensure artifacts exist

Check for `target/manifest.json`. If it doesn't exist, the user needs to run a dbt command first:

```bash
dbt parse    # minimal — produces manifest.json only
dbt build    # full — produces manifest.json + run_results.json
dbt docs generate  # produces catalog.json with column metadata for all columns
```

Different artifacts populate different parts of the index:
- `manifest.json` (required) — nodes, edges, columns, semantic layer
- `catalog.json` (optional) — warehouse column types, stats, profiling
- `run_results.json` (optional) — execution results, timing, test failures
- `sources.json` (optional) — source freshness results
- `semantic_manifest.json` (optional) — MetricFlow definitions

### Step 2 — Ingest

```bash
dbt-index ingest
```

By default, `ingest` reads from `target/`. Use `--target` to specify a different target directory:

```bash
dbt-index ingest --target /path/to/target
```

Use `--full-refresh` to bypass content hashing and re-ingest all rows. Forces a full re-read of all artifacts, ignoring the hash cache. Useful if the index gets into a bad state:

```bash
dbt-index ingest --full-refresh
```

### Step 3 — Verify

```bash
dbt-index status
```

## Keeping the index fresh

After any `dbt build`, `dbt run`, `dbt test`, or `dbt docs generate`, re-run `dbt-index ingest` to pick up new artifacts. Content hashing skips unchanged rows, so re-ingestion is fast.

Alternatively, add `--auto-reingest` to any subcommand which will re-ingest if the artifacts have changed:

```bash
dbt-index <subcommand> --auto-reingest
```
