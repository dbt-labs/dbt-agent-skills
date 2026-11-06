# Functions and Syntax

## Functions Lake Compute lacks (`function:<name>`)

The switch already rewrites these when it can type the columns they read:
`iff`, `nvl`, `nvl2`, `zeroifnull`, `nullifzero`, `div0`, `charindex`,
`startswith`, `try_to_number` (with one argument), `boolor_agg`,
`booland_agg`, `array_size`, `datediff` (day, month, quarter and year parts,
between dates: cast timestamps with `::date`), and some date functions. Look for them
in the model's `rewrite.fragments`, and leave them to the switch.

For the rest, find a DuckDB function that means the same thing:

| Snowflake | Lake Compute (DuckDB) | Both? |
|---|---|---|
| `iff(c, a, b)` | `case when c then a else b end` | yes |
| `nvl(a, b)`, `ifnull(a, b)` | `coalesce(a, b)` | yes |
| `charindex(s, t)` | `position(s in t)` | yes |
| `listagg(x, ',') within group (order by y)` | `string_agg(x, ',' order by y)` | no |
| `array_size(a)` | `len(a)` | no |
| `try_to_number(s, p, s2)` | `try_cast(s as decimal(p, s2))` (rounds, and is NULL when it doesn't fit, as `try_to_number` is) | yes |
| `regexp_substr(s, p)` | `nullif(regexp_extract(s, p), '')` (`regexp_extract` returns `''` where Snowflake returns NULL) | no |
| `split_part(s, d, n)` | `split_part(s, d, n)` | yes |

A form both engines take can land before the switch. A Lake Compute-only form
must land with it.

## Types (`type:<name>`)

Cast to a type Lake Compute's DuckDB has: `varchar` for `text`/`string`,
`decimal(p, s)` for `number(p, s)`, `timestamp` for `timestamp_ntz`. A
`variant` cast is fine: Lake Compute has `VARIANT`, even when the check calls
the result inconclusive.

## Other Snowflake-only syntax (`syntax:*`)

| Key | Rewrite |
|---|---|
| `syntax:ignore_nulls` | Put `IGNORE NULLS` inside the call: `last_value(x ignore nulls) over (...)` |
| `syntax:within_group` | `string_agg(x, sep order by y)` |
| `syntax:like_any` | `a like 'x%' or a like 'y%'` |
| `syntax:flatten` | `unnest(...)`: see [semi-structured access](semi-structured.md) |
| `syntax:other` | Read the `message`: it names where the parser stopped |

After each edit, check the model again. The check stops at the first
problem, so a fix can reveal the next one.
