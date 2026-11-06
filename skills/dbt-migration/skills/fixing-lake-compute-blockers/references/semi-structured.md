# Semi-structured Access (`syntax:semi_structured`)

Snowflake reads fields of `VARIANT` and `OBJECT` values with a colon path:
`payload:status`, `"enrichment":"client_ip":"geo"`. Lake Compute's DuckDB
can't parse it.

## The switch rewrites colon paths

`dbt init lakecompute` rewrites each colon path as bracket access, which
Snowflake and Lake Compute's DuckDB both read the same way from a `VARIANT`:

| Before (Snowflake only) | After (both) |
|---|---|
| `payload:status` | `payload['status']` |
| `payload:status::varchar` | `payload['status']::varchar` |
| `"enrichment":"client_ip":"geo"` | `"enrichment"['client_ip']['geo']` |

Find them in the model's `rewrite.fragments` (`function: "colon path"`), and
leave them to `--switch`. Keys keep their case: a field name is
case-sensitive on both engines.

## What it doesn't rewrite

The switch rewrites a model's SQL whole or not at all. When the issue's
`message` says `not rewritten: ...`, it rewrites none of that model's colon
paths: change each one to bracket access by hand, then handle what stopped
the rewrite:

- **An array index.** `arr[0]` works in both, but Snowflake counts from 0 and
  DuckDB from 1. Add 1 for Lake Compute: `payload:items[0]` becomes
  `payload['items'][1]`. Land the edit with the switch.
- **`LATERAL FLATTEN(input => arr)`.** It has no shared form. On Lake Compute,
  use `unnest(arr)`. Land the edit with the switch.

## Then check again

Run the check on the model. If it still fails, the column's type on Lake
Compute decides the form:

- A `VARIANT` or a `STRUCT` column: bracket access works.
- JSON text (a `VARCHAR` holding JSON): bracket access returns the field with
  its quotes. Use `json_extract_string(col, '$.client_ip.geo')`. Snowflake
  doesn't have it: land the edit with the switch.

The check's `message` names what the binder saw. When in doubt, ask the user
how the column is stored in Iceberg.
