# Snowflake SQL in dbt Models

## Features worth using

| Feature | Example | Note |
|---|---|---|
| `QUALIFY` | `qualify row_number() over (partition by order_id order by updated_at desc nulls last, loaded_at desc) = 1` | keeps the latest row per key without a subquery; `nulls last` so an undated row never wins, plus a deterministic tie-break |
| `SELECT * EXCLUDE` | `select * exclude (_loaded_at) from …` | drop columns without listing the rest |
| `SELECT * REPLACE` | `select * replace (coalesce(is_active, false) as is_active) from …` | change one column in place |
| `GROUP BY ALL` | `select order_date, count(*) from … group by all` | groups by every non-aggregate column; safer than positional `group by 1, 2` when columns move |
| `DATEDIFF` / `DATEADD` | `datediff('hour', ordered_at, shipped_at)` | elapsed time between timestamps |
| `GET_DDL` | `get_ddl('VIEW', '<db>.<schema>.<name>')` | inspect the DDL of an object, also in tests |

Lateral column aliases (`select a + b as s, s * 2 as d`) work in Snowflake but not in every warehouse; avoid them in models that may move to another platform.

## NULL and counting semantics

- `count(expr)` counts non-NULL values: `count(case when c then 1 else 0 end)` counts every row. Use `sum(case when c then 1 else 0 end)` or omit the `else`.
- `x != true` is NULL when `x` is NULL, so the row is filtered out. Use `x is distinct from true`.
- Compare values that may be NULL with `is distinct from` / `is not distinct from`, also in singular tests: `where a != b` lets a NULL on either side pass silently.
- `avg` skips NULLs; do not `coalesce(x, 0)` before averaging.
- Default counts to 0, keep rates NULL: `coalesce(rate, 0)` turns "no data" into "0%".
- Division: `a / nullif(b, 0)`, or `div0null(a, b)`.

## Identifiers and case

Snowflake folds unquoted identifiers to **uppercase**. Keep model and column names unquoted `snake_case`; a quoted identifier (`"orderId"`) must then be quoted with the same case everywhere. String comparisons are case sensitive: `'Closed won' <> 'Closed Won'`.

## Types and time

- `timestamp_ntz` for UTC instants stored without a zone; `timestamp_tz` or `convert_timezone` when the zone matters.
- Store UTC and convert at presentation. A fixed UTC offset and a zone with daylight saving give different local hours for part of the year.
- Cast text to a type only after filtering to the rows that hold that type, for example in a key-value column.

## Compile errors

| Error (shape) | Cause |
|---|---|
| `syntax error ... unexpected 'select'` | a trailing comma after the last CTE |
| `too many arguments for function DATE_TRUNC` | `date_trunc` takes exactly two arguments; for elapsed time use `datediff` |
| `invalid identifier 'CTE.ALIAS'` | an alias defined in the same `select` referenced as a column of the CTE |
| `... is not a valid group by expression` | aggregates mixed with plain columns and no `group by` |

Snowflake often reports one compile error at a time. Fix it and run again to reach the next; do not assume the first error is the only one.

## Debugging a model

1. Preview the compiled SQL: `dbt show --select <model> --limit 50`.
2. Count at each CTE: `select count(*), count(distinct <key>)`.
3. Compare one metric with a count you can make by hand for one day or one key.
