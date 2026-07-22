---
name: migrating-dbt-1.3
description: Upgrade a dbt project from dbt-core 1.3 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.3.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.3 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.3** to **1.8**
(the entry point of the latest release track). A 1.3 project takes five hops to
reach 1.8 (1.3→1.4, 1.4→1.5, 1.5→1.6, 1.6→1.7, 1.7→1.8), so this migration applies
changes from every hop. Apply every change below that is present in the project,
then verify the project parses under 1.8. Make only the changes required by this
upgrade — do not refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Pin Python model materializations that relied on the `view` default (1.3→1.4, behavior)

In 1.4 the default materialization for Python models (`.py` models with a
`def model(dbt, session)` and no explicit `materialized` config) changed from
`view` to `table`. On 1.3 such a model built as a view; from 1.4 on it builds as
a table — a physically different object with different storage and refresh
semantics, and every downstream `ref()` now resolves to a table.

Find every Python model that has no explicit materialization. If a model relied
on the old `view` default, set it explicitly:

```python
def model(dbt, session):
    dbt.config(materialized="view")
    ...
```

Models that are fine as tables need no change — the point is to make the choice
explicit so the upgrade does not silently swap the materialization out from under
downstream consumers.

### 2. Find alternative approaches for `on-run-start`/`on-run-end` hooks that must abort a run (1.3→1.4, behavior)

Before 1.4, a failing `on-run-start` or `on-run-end` hook halted the run (the
error was re-raised). From 1.4, a failing hook is recorded as an error result but
**no longer stops the run** — everything after it still executes.

Find every `on-run-start` / `on-run-end` hook in `dbt_project.yml`. If a hook is a
**guard or circuit-breaker** — it exists specifically to stop the run when a
precondition fails (e.g. a freshness check, an environment assertion) — flag it to
the user: on 1.4+ it no longer aborts anything, so the guard is silently inert.

**Ask the user how they want to restore the guard behavior** rather than picking
for them; options depend on what the hook checks:
- Move the check into a `dbt build`/`dbt test` step (e.g. a singular test or a
  `dbt-utils` assertion) so a failure fails the invocation via the normal
  test-failure path.
- Wrap the hook's logic in a macro that raises via `{{ exceptions.raise_compiler_error(...) }}`
  at compile/parse time instead of run time, if the check can run that early.
- If the hook doesn't actually need to abort anything (e.g. it's logging or
  best-effort cleanup), no change is needed — note that explicitly so the user
  knows it was reviewed.

Hooks that don't need to abort the run need no change.

### 3. Verify underscore-form `pre_hook`/`post_hook` behavior if they use Jinja (1.3→1.4, behavior)

Before 1.4, only the hyphenated `pre-hook`/`post-hook` keys were correctly
**late-rendered** (their Jinja evaluated at run time, with full runtime context).
The underscore form `pre_hook`/`post_hook` had the same intent but was not
late-rendered — its Jinja evaluated too early. From 1.4, both forms are
late-rendered consistently.

Find every model/seed/snapshot `config()` (or `dbt_project.yml` default) using
the **underscore** form (`pre_hook`/`post_hook`) whose value contains Jinja (`{{ }}`
or `{% %}`) — not a plain SQL string. For each one, check whether the Jinja
references anything that is only available at run time (e.g. `run_started_at`,
`invocation_id`, `this`, macro calls that depend on state set during the run).

- If the hook's Jinja only used static/compile-time values, there is no
  behavior change — the later render still resolves to the same string.
- If the hook's Jinja depends on run-time state, the resolved value on 1.4+ may
  differ from what ran on 1.3 (it previously rendered against parse-time context,
  possibly incorrectly). **Ask the user to confirm** the hook still does what
  they intend once it evaluates at the correct time.

### 4. Apply the 1.4→1.8 changes

The rest of this migration continues from the 1.4→1.8 hop. Execute the skill
`migrating-dbt-1.4` for this hop.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. A
clean parse (no errors, no deprecation warnings) means the migration succeeded.
If the parse fails, read the error and fix the specific resource it names, then
parse again.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`,
or `dbt compile`, and do not query any warehouse. Those touch data and are
validated separately — they are out of scope here. `dbt parse` is purely static
and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the
project root summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Create a section for this version hop and describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one
entry per change. If there's an existing `migration_changes.md` prepared by a
previous version hop, append to the doc.
