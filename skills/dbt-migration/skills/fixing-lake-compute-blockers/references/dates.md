# Dates and Times

## A date part written as a name (`syntax:date_part_name`)

`datediff(day, a, b)`, `date_trunc(quarter, ts)`, `dateadd(month, 1, d)`:
DuckDB reads the bare name as a column. Quote it. Both engines take a
quoted part:

| Before | After (both) |
|---|---|
| `datediff(day, a, b)` | `datediff('day', a, b)` |
| `date_trunc(quarter, ts)` | `date_trunc('quarter', ts)` |
| `date_part(dow, d)` | `date_part('dow', d)` |

`datediff` counts the part boundaries crossed on both engines, so its result
doesn't change.

## `date_trunc` of a DATE (`type:date_trunc_date`)

On Lake Compute, `date_trunc` of a DATE returns a TIMESTAMP; Snowflake returns
a DATE. The values match, but the column's type changes. Cast it back. Both
engines take the cast:

```sql
cast(date_trunc('month', order_date) as date) as order_month
```

## `dateadd` (`function:dateadd`)

Lake Compute's DuckDB has no `dateadd`. Rewrite it with interval arithmetic.
With a constant amount, write the interval quoted: both engines take
`interval '1 day'` (not `interval 1 day`, which Snowflake rejects), so the
edit can land before the switch:

| Before | After | Both? |
|---|---|---|
| `dateadd('day', -1, ts)` | `ts - interval '1 day'` | yes |
| `dateadd('hour', 5, ts)` | `ts + interval '5 hours'` | yes |
| `dateadd('day', n, d)` on a DATE | `d + n` (a DATE stays a DATE) | yes |
| `dateadd('month', 1, d)` on a DATE | `cast(d + interval '1 month' as date)` | yes |
| `dateadd('day', n, ts)`, `n` a column | `ts + n * interval '1 day'` | no: land with the switch |

A month added to the 31st lands on the month's last day on both engines.

The common case is an incremental filter:

```sql
{% if is_incremental() %}
  where updated_at >= (select max(updated_at) from {{ this }}) - interval '1 day'
{% endif %}
```

## `to_date` (`function:to_date`)

| Before | After |
|---|---|
| `to_date(s)` (ISO text) | `cast(s as date)` (both) |
| `to_date(ts)` | `cast(ts as date)` (both) |
| `to_date(s, 'MM/DD/YYYY')` | `strptime(s, '%m/%d/%Y')::date` (Lake Compute only: land with the switch) |

## Zoned timestamps

The switch doesn't rewrite date functions over `TIMESTAMP_TZ` or
`TIMESTAMP_LTZ` columns. Their day boundaries depend on the session's time
zone, and Lake Compute's is UTC. Ask the user which zone the model means, and
convert explicitly before truncating or comparing days.
