# Generating Explores and Joins

An `explore:` in LookML is a join graph. A fact model is almost always the base of an explore; dim models are the tables it joins out to. Every join below is a **suggestion to confirm with the user**, not something to write into the file automatically.

## Finding join candidates

For the fact model you just built a view for, look at its columns for foreign keys — typically an `_id` column that isn't the table's own primary key:

```yaml
# fct__salesforce_activity
columns:
  - name: activity_id       # primary key of this table
  - name: opportunity_id    # looks like a foreign key
  - name: activity_type
  - name: logged_at
```

For each FK candidate, check whether a corresponding dim model exists:

1. **Check for a `relationships` test** — the strongest signal:
   ```yaml
   - name: opportunity_id
     data_tests:
       - relationships:
           to: ref('dim__salesforce_opportunities')
           field: opportunity_id
   ```
   If this exists, the join is confirmed by dbt itself — use the `to`/`field` values directly as the `sql_on:`.

2. **If no `relationships` test exists**, fall back to the naming heuristic: an FK column named `opportunity_id` strongly suggests a `dim__..._opportunities` (or similarly named) model exists. Check for it. If found, this is still just a **suggestion** — present it to the user rather than assuming the relationship is correct, since naming similarity isn't a guarantee the columns mean the same thing.

3. **If neither signal exists**, don't invent a join — mention that you didn't find a confirmed or plausible relationship for that column, in case the user knows of one you can't see from the files alone.

## Presenting the suggestion

State it plainly, e.g.:

> `fct__salesforce_activity` has an `opportunity_id` column. `dim__salesforce_opportunities` exists and has a matching `unique` + `not_null` test on `opportunity_id`. Joining it would let you slice activity by opportunity name, owner, and stage. Add this join to the explore?

Only write the `join:` block after the user confirms.

## Join type and relationship

- Default to `type: left_outer` for fact → dim joins, so fact rows with a null FK aren't dropped.
- Set `relationship:` based on what's actually true of the join key on the dim side:
  - If the dim's join column has a `unique` test → `relationship: many_to_one`.
  - If it doesn't, don't assert `many_to_one` — flag that the relationship's cardinality isn't confirmed, since an unconfirmed `many_to_one` on a non-unique key will silently fan out rows and inflate every measure in the explore.

## Example

Given the `relationships` test above, plus a `unique` test on `dim__salesforce_opportunities.opportunity_id`:

```lkml
explore: fct__salesforce_activity {
  join: dim__salesforce_opportunities {
    type: left_outer
    sql_on: ${fct__salesforce_activity.opportunity_id} = ${dim__salesforce_opportunities.opportunity_id} ;;
    relationship: many_to_one
  }
}
```

## Dim models generally don't need their own explore

A dim model is usually only explored through the fact tables that join to it. Don't create a standalone explore for a dim model unless the user specifically asks to browse it on its own.
