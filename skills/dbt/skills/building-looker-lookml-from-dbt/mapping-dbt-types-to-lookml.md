# Mapping dbt Column Types to LookML

Use this table to translate a column's warehouse data type into a LookML dimension `type:`. Prefer the type declared in the model's YAML (`data_tests`/`data_type` under `columns:`); if it isn't declared, introspect with `dbt show --select <model> --limit 1` or a warehouse `information_schema` query rather than guessing from the column name.

## General mapping

| Source type | LookML `type:` | Notes |
| --- | --- | --- |
| `varchar`, `text`, `string`, `char` | `string` | Default case |
| `boolean`, `bool` | `yesno` | LookML has no plain `boolean` dimension type |
| `integer`, `bigint`, `smallint`, `int` | `number` | Do not add `value_format_name` unless the column is a measure of currency/percent |
| `decimal`, `numeric`, `float`, `double precision`, `real` | `number` | Consider `value_format_name` if the YAML description implies currency, percent, etc. |
| `date` | `dimension_group`, `type: time`, `datatypes: [date]` | `timeframes: [date, week, month, quarter, year]` is a reasonable default |
| `timestamp`, `timestamptz`, `datetime` | `dimension_group`, `type: time`, `datatypes: [datetime]` (or `epoch` if stored as unix time) | `timeframes: [raw, time, date, week, month, quarter, year]` |
| `json`, `jsonb`, `variant`, `object`, `struct` | `string` (usually) | Flag for manual review — nested/semi-structured columns often need per-key dimensions rather than a single dump; don't silently serialize the whole blob into one dimension without asking |
| `array`, `list` | Flag for manual review | LookML has no native array type; needs either an unnest step upstream in dbt or an explicit decision on how to represent it |

## Redshift-specific types

| Redshift type | LookML `type:` | Notes |
| --- | --- | --- |
| `super` | Flag for manual review | Same reasoning as JSON above — don't guess a flattening strategy |
| `geometry`, `geography` | Flag for manual review | No first-class LookML geo dimension type; typically extract lat/lon as separate `number` dimensions upstream in dbt, then map those |
| `varchar(n)` | `string` | The length constraint doesn't need to be reflected in LookML |
| `timestamp` vs `timestamptz` | Both → `dimension_group` (`type: time`) | If the warehouse column is `timestamptz`, note the timezone handling in the dimension's `description` so downstream users aren't surprised by conversion behavior |

## Naming and grouping

- A raw timestamp/date column should never appear as a standalone `dimension:` — it should always be wrapped as a `dimension_group` so Looker generates the `_date`, `_week`, `_month`, etc. variants automatically.
- Name the dimension group after the column with the type suffix stripped (e.g. `created_at` → `dimension_group: created`), matching Looker's own generator convention, so the generated fields read as `created_date`, `created_month`, etc.
- Boolean columns modeled as `is_*` or `has_*` in dbt should keep that prefix in the LookML dimension name — don't rename them.

## When `meta.looker` is present

If the model's YAML has:

```yaml
columns:
  - name: order_status
    data_type: varchar
    meta:
      looker:
        value_format_name: id
        hidden: true
```

Apply every key under `meta.looker` directly onto the generated dimension, overriding whatever the table above would otherwise produce. This block exists specifically so analytics engineers can correct cases the generator gets wrong — never override it with an inferred default.
