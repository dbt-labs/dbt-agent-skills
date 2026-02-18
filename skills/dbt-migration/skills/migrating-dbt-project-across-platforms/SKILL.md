---
name: migrating-dbt-project-across-platforms
description: Use when migrating a dbt project from one data platform or data warehouse to another (e.g., Snowflake to Databricks, Databricks to Snowflake) using dbt Fusion's real-time compilation to identify and fix SQL dialect differences.
metadata:
  author: dbt-labs
---

# Migrating a dbt Project Across Data Platforms

This skill guides migration of a dbt project from one data platform (source) to another (target) — for example, Snowflake to Databricks, or Databricks to Snowflake.

**The core approach**: dbt Fusion compiles SQL in real-time and produces rich, detailed error logs that tell you exactly what's wrong and where. We trust Fusion entirely for dialect conversion — no need to pre-document every SQL pattern difference. The workflow is: read Fusion's errors, fix them, recompile, repeat until done. Combined with dbt unit tests (generated on the source platform before migration), we prove both **compilation correctness** and **data correctness** on the target platform.

**Success criteria**: Migration is complete when:
1. `dbtf compile` finishes with 0 errors **and 0 warnings** on the target platform
2. All unit tests pass on the target platform (`dbt test --select test_type:unit`)
3. All models run successfully on the target platform (`dbtf run`)

**Validation cost**: Use `dbtf compile` as the primary iteration gate — it's free (no warehouse queries) and catches both errors and warnings from static analysis. Only `dbtf run` and `dbt test` incur warehouse cost; run those only after compile is clean.

## Contents

- [Additional Resources](#additional-resources) — Reference docs for installation, unit tests, profile targets
- [Migration Workflow](#migration-workflow) — 7-step migration process with progress checklist
- [Don't Do These Things](#dont-do-these-things) — Critical guardrails
- [Known Limitations & Gotchas](#known-limitations--gotchas) — Fusion-specific and cross-platform caveats

## Additional Resources

- [Installing dbt Fusion](references/installing-dbt-fusion.md) — How to install and verify dbt Fusion
- [Generating Unit Tests](references/generating-unit-tests.md) — How to generate unit tests on the source platform before migration
- [Switching Targets](references/switching-targets.md) — How to configure the dbt target for the destination platform and update sources

## Migration Workflow

### Progress Checklist

Copy this checklist to track migration progress:

```
Migration Progress:
- [ ] Step 1: Verify dbt Fusion is installed and working
- [ ] Step 2: Assess source project (dbtf compile — 0 errors on source)
- [ ] Step 3: Generate unit tests on source platform
- [ ] Step 4: Switch dbt target to destination platform
- [ ] Step 5: Run Fusion compilation and fix all errors (dbtf compile — 0 errors on target)
- [ ] Step 6: Run and validate unit tests on target platform
- [ ] Step 7: Final validation and document changes in migration_changes.md
```

### Instructions

When a user asks to migrate their dbt project to a different data platform, follow these steps. Create a `migration_changes.md` file documenting all code changes (see template below).

#### Step 1: Verify dbt Fusion is installed

Fusion is **required** — it provides the real-time compilation and rich error diagnostics that power this migration. Fusion may be available as `dbtf` or as `dbt`.

To detect which command to use:
1. Check if `dbtf` is available — if it exists, it's Fusion
2. If `dbtf` is not found, run `dbt --version` — if the output starts with `dbt-fusion`, then `dbt` is Fusion

Use whichever command is Fusion everywhere this skill references `dbtf`. If neither provides Fusion, guide the user through installation. See [references/installing-dbt-fusion.md](references/installing-dbt-fusion.md) for details.

#### Step 2: Assess the source project

Run `dbtf compile` on the **source** platform target to confirm the project compiles cleanly with 0 errors. This establishes the baseline.

```bash
dbtf compile
```

If there are errors on the source platform, those must be resolved first before starting the migration. The `migrating-dbt-core-to-fusion` skill can help resolve Fusion compatibility issues.

#### Step 3: Generate unit tests on source platform

While still connected to the **source** platform, generate dbt unit tests for key models to capture expected data outputs as a "golden dataset." These tests will prove data consistency after migration.

**Which models to test**: You **must** test **every leaf node** — models at the very end of the DAG that no other model depends on via `ref()`. Do not guess leaf nodes from naming conventions — derive them programmatically using the methods in [references/generating-unit-tests.md](references/generating-unit-tests.md#identifying-leaf-nodes). List all leaf nodes explicitly and confirm the count before writing tests. Also test any mid-DAG model with significant transformation logic (joins, calculations, case statements).

**How to generate tests**:

1. Identify leaf nodes: `dbt ls --select "+tag:core" --resource-type model` or inspect the DAG
2. Use `dbt show --select model_name --limit 5` to preview output rows on the source platform
3. Pick 2-3 representative rows per model that exercise key business logic
4. Write unit tests in YAML using the `dict` format — see the `adding-dbt-unit-test` skill for detailed guidance on authoring unit tests
5. Place unit tests in the model's YAML file or a dedicated `_unit_tests.yml` file

See [references/generating-unit-tests.md](references/generating-unit-tests.md) for detailed strategies on selecting test rows and handling complex models.

**Verify tests pass on source**: Run `dbt test --select test_type:unit` on the source platform to confirm all unit tests pass before proceeding.

#### Step 4: Switch dbt target to destination platform

Add a new target output for the destination platform within the existing profile in `profiles.yml`, then set it as the active target. Do **not** change the `profile` key in `dbt_project.yml`.

1. Add a new output entry in `profiles.yml` under the existing profile for the destination platform
2. Set the `target:` key in the profile to point to the new output
3. Update source definitions (`_sources.yml`) if the database/schema names differ on the destination platform
4. Remove or update any platform-specific configurations (e.g., `+snowflake_warehouse`, `+file_format: delta`)

See [references/switching-targets.md](references/switching-targets.md) for detailed guidance.

#### Step 5: Run Fusion compilation and fix errors

This is the core migration step. First, clear the target cache to avoid stale schema issues from the source platform, then run `dbtf compile` against the target platform — Fusion will flag every dialect incompatibility at once.

```bash
rm -rf target/
dbtf compile
```

**How to work through errors**:

1. **Read the error output carefully** — Fusion's error messages are rich and specific. They tell you the exact file, line number, and nature of the incompatibility.
2. **Group similar errors** — Many errors will be the same pattern (e.g., the same unsupported function used in multiple models). Fix the pattern once, then apply across all affected files.
3. **Fix errors iteratively** — Make fixes, recompile, check remaining errors. Summarize progress (e.g., "Fixed 12 errors, 5 remaining").
4. **Common categories of errors**:
   - **SQL function incompatibilities** — Functions that exist on one platform but not another (e.g., `GENERATOR` on Snowflake vs. `sequence` on Databricks, `nvl2` vs. `CASE WHEN`)
   - **Type mismatches** — Data type names that differ between platforms (e.g., `VARIANT` on Snowflake vs. `STRING` on Databricks)
   - **Syntax differences** — Platform-specific SQL syntax (e.g., `FLATTEN` on Snowflake vs. `EXPLODE` on Databricks)
   - **Unsupported config keys** — Platform-specific dbt config like `+snowflake_warehouse` or `+file_format: delta`
   - **Macro/package incompatibilities** — Packages that behave differently across platforms

**Trust Fusion's errors**: The error logs are the primary guide. Do not try to anticipate or pre-fix issues that Fusion hasn't flagged — this leads to unnecessary changes. Fix exactly what Fusion reports.

Continue iterating until `dbtf compile` succeeds with **0 errors and 0 warnings**. Warnings become errors in production — treat them as blockers. Common warnings to resolve:

- **dbt1065 (unspecified numeric precision)**: Aggregations like `SUM()` on Snowflake produce `NUMBER` with unspecified precision/scale, risking silent rounding. Fix by casting: `cast(sum(col) as decimal(18,2))`. This is a cross-platform issue — Databricks doesn't enforce this, Snowflake does.
- **dbt1005 (package missing dbt_project.yml)**: Caused by platform-specific packages (e.g., `spark_utils`, `dbt-databricks`) that are no longer needed on the target. Remove them from `packages.yml` and any associated config (e.g., `dispatch` blocks, `+file_format: delta`). Also check `dbt_packages/` for stale installed packages and re-run `dbtf deps` after changes.
- **Adapter warnings from profiles.yml**: If the user's `profiles.yml` contains profiles for multiple platforms (e.g., both `snowflake_demo` and `databricks_demo`), Fusion may load adapters for all profiles and warn about unused ones. These are non-actionable at the project level — inform the user but don't count them as blockers.

#### Step 6: Run and validate unit tests

With compilation succeeding, run the unit tests that were generated in Step 3:

```bash
dbt test --select test_type:unit
```

If tests fail:
- **Data type differences** — The target platform may represent types differently (e.g., decimal precision, timestamp formats). Adjust expected values in unit tests to match target platform behavior.
- **Floating point precision** — Use `round()` or approximate comparisons for decimal columns.
- **NULL handling** — Platforms may differ in how NULLs propagate through expressions. Update test expectations accordingly.
- **Date/time formatting** — Default date formats may differ. Ensure test expectations use the target platform's default format.

Iterate until all unit tests pass.

#### Step 7: Final validation and documentation

If you already ran `dbtf run` (to materialize models for unit testing) and all unit tests passed, the migration is proven — don't repeat work with a redundant `dbtf build`. If you haven't yet materialized models, run `dbtf build` to do everything in one step. Verify all three success criteria (defined above) are met.

Document all changes in `migration_changes.md` using the template below. Summarize the migration for the user, including:
- Total number of files changed
- Categories of changes made
- Any platform-specific trade-offs or notes

### Output Template for migration_changes.md

Use this structure when documenting migration changes:

```markdown
# Cross-Platform Migration Changes

## Migration Details
- **Source platform**: [e.g., Snowflake]
- **Target platform**: [e.g., Databricks]
- **dbt project**: [project name]
- **Total models migrated**: [count]

## Migration Status
- **Final compile errors**: 0
- **Final unit test failures**: 0
- **Final build status**: Success

## Configuration Changes

### dbt_project.yml
- [List of config changes]

### Source Definitions
- [List of source definition changes]

### Target Changes
- [Target configuration details]

## Package Changes
- [Any package additions, removals, or version changes]

## Unit Test Adjustments
- [Any changes made to unit tests to accommodate platform differences]

## Notes for User
- [Any manual follow-up needed]
- [Known limitations or trade-offs]
```

## Don't Do These Things

1. **Don't pre-fix issues that Fusion hasn't flagged.** Fusion's error output is the source of truth. Making speculative changes leads to unnecessary modifications and potential regressions. Fix only what Fusion reports.
2. **Don't try to document every possible SQL dialect difference.** There are thousands of platform-specific SQL nuances. Fusion knows them all. Let Fusion find the issues; your job is to fix what it reports.
3. **Don't skip unit tests.** Compilation success alone doesn't prove the migration is correct. Unit tests verify that the data outputs are consistent between platforms — this is the proof that the migration preserves business logic.
4. **Don't modify unit test expectations unless there's a legitimate platform difference.** If a unit test fails, first check if the model logic needs fixing. Only adjust test expectations for genuine platform behavioral differences (e.g., decimal precision, NULL handling). If you modified a unit test, let the user know.
5. **Don't remove models or features without user approval.** If a model can't be migrated (e.g., it uses a platform-specific feature with no equivalent), inform the user and let them decide.
6. **Don't change the data architecture.** The migration should preserve the existing model structure, materializations, and relationships. Platform migration is a dialect translation, not a refactoring opportunity.
7. **Don't use `dbtf run` for iterative validation.** It costs warehouse compute. Use `dbtf compile` (free) to iterate on fixes. Only run `dbtf run` and `dbt test` once compile is fully clean.

## Known Limitations & Gotchas

### Fusion-specific
- **Clear the target cache when switching platforms.** Run `rm -rf target/` before compiling against a new platform. Fusion caches warehouse schemas in the target directory, and stale schemas from the source platform can cause false column-not-found errors.
- **Versioned models and unit tests.** As of Fusion 2.0, unit tests on versioned models (models with `versions:` in their YAML) may fail with `dbt1048` errors. Workaround: test non-versioned models, or test versioned models through their non-versioned intermediate dependencies.
- **`dbtf show --select` validates against warehouse schema.** If models haven't been materialized on the target platform yet, use `dbtf show --inline "SELECT ..."` for direct warehouse queries instead.
- **Python models: Fusion validates `dbt.ref()` even when disabled.** Disabling a Python model does not prevent Fusion from validating its `dbt.ref()` calls (`dbt1062`). Workaround: comment out the `dbt.ref()` lines or remove the Python models if they're not relevant to the migration.
- **See the full list of Fusion limitations** at https://docs.getdbt.com/docs/fusion/supported-features#limitations — these must be adhered to since Fusion is required for this workflow.

### Cross-platform data differences
- **Sample datasets may differ between platforms.** Even "standard" datasets like TPCH can have minor schema or data differences across platforms (e.g., column names, data types, row counts). When using sample data for migration testing, verify the source data schema on both platforms before assuming 1:1 equivalence.
- **Platform-specific config keys are not errors until Fusion flags them.** Keys like `snowflake_warehouse` or `cluster_by` won't cause Fusion compile errors on the source platform — they'll only surface when compiling against the target. Don't pre-remove them.
