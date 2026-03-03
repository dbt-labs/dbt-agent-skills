# Fusion Migration Triage — Category D: Engine Bug (Truly Blocked)

## Background

A user is migrating their dbt project to Fusion. They ran `dbt build` and seeds are failing with syntax errors. This is caused by a known Fusion engine bug (dbt-labs/dbt-fusion#1345): Fusion dispatches seed nodes to the `materialization_table_default` macro instead of `materialization_seed_default`, causing CSV content to be embedded as raw SQL in a `CREATE TABLE AS (...)` statement.

There is NO user-side workaround for this. The user cannot fix how Fusion dispatches materializations. The only option is to wait for the Fusion engine fix.

The `dbt_compile_output.txt` file contains the pre-captured error output.

## Expected Outcome

The agent should:
1. Classify the error as Category D (blocked, not fixable in project)
2. Recognize this as a Fusion engine bug, not a user code error
3. NOT suggest modifying user code, removing seeds, or any workaround
4. Reference or search for the relevant GitHub issue
5. Clearly communicate that this requires a Fusion engine update

## Grading Criteria

- [ ] correct_category: Classified as Category D (blocked) — not A, B, or C
- [ ] recognized_engine_bug: Identified this as a Fusion engine bug in materialization dispatch, not a user error
- [ ] no_fix_attempted: Did NOT suggest modifying seed files, SQL, or project config to work around this
- [ ] no_destructive_suggestion: Did NOT suggest removing seeds or switching to a different loading strategy as a "fix"
- [ ] communicated_blocker: Clearly told the user this requires a Fusion update and is not fixable in their project
