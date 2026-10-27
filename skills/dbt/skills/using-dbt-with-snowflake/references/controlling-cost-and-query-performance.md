# Controlling Cost and Query Performance on Snowflake

Snowflake bills **warehouse running time** (credits per second while the warehouse runs, with a 60-second minimum each time it starts), not bytes scanned. Every optimisation works by making the warehouse read less, compute less, or run for less time.

## 1. Measure first

Find the queries that cost the most, then find out why:

```sql
-- credits per query over the last 7 days (latency up to 8 hours; excludes idle time and queries of ~100 ms or less)
select
    q.query_id,
    q.warehouse_name,
    q.query_tag,
    q.credits_attributed_compute
from snowflake.account_usage.query_attribution_history q
where q.start_time >= dateadd(day, -7, current_timestamp())
order by q.credits_attributed_compute desc
limit 50;
```

- Rank by total cost: runtime × frequency. A 2-minute model run 500 times a day matters more than a 20-minute monthly one.
- Tag dbt queries so cost can be attributed: the `query_tag` config in `profiles.yml` or per folder (`+query_tag: dbt_marts`).
- Before running: `explain` shows partitions assigned vs total per scan. After running: the Query Profile in Snowsight.

| In the Query Profile | Meaning | Go to |
|---|---|---|
| partitions scanned close to partitions total | pruning does not work | 2 |
| bytes spilled to local or remote storage | not enough memory | 3, 5 |
| a join returns far more rows than it receives | the join multiplies rows | 3 |
| high queued time | the warehouse is overloaded | 5 |
| repeated queries with a low share scanned from cache | the cache is cold | 4 |

## 2. Read less data

- **Filter the raw column with a plain range.** Functions hide the column from the partition metadata: `where year(order_date) = 2026` may not prune; `where order_date >= '2026-01-01' and order_date < '2027-01-01'` always can.
- **Filter as early as correctness allows.** Simple filters are pushed into CTEs automatically, but not past a window function, `QUALIFY`, `GROUP BY`, `DISTINCT`, `LIMIT` or the NULL side of an outer join. When you know it is safe, filter in the same CTE as the window function.
- **Filter every large table on its own column.** A filter on table A only removes rows of table B during the join, after B was read.
- **Select only the needed columns**, especially in models materialized as tables: `create table as select *` writes every column.
- **Match data types** in filters and join keys; a number compared with text forces conversions that can block pruning.

## 3. Joins and aggregation

- **Check for joins that multiply rows.** If a join returns far more rows than its inputs, the keys are not unique where you assumed. Fix the keys; a final `distinct` hides the problem after the cost has been paid.
- **Aggregate before joining** when the join only adds descriptive columns.
- `union all` instead of `union` unless duplicates must go; no `order by` inside CTEs.
- `approx_count_distinct` on very large tables when about 2% error is acceptable.

## 4. Caches and metadata

- **Result cache:** an identical query on unchanged data returns from the result cache for 24 hours without a running warehouse. Keep dashboard queries identical between runs and avoid per-run values such as `current_timestamp()` in them.
- **Warehouse cache:** cleared when the warehouse suspends. A BI warehouse that repeats the same queries can be cheaper with a longer `auto_suspend`; a dbt warehouse stays short.
- **Metadata:** `count(*)`, `min` and `max` over a whole table are answered from metadata without scanning, so cheap source checks are fine on Snowflake.

## 5. Warehouse size and setup

- **Spilling → size up.** Each size doubles memory and local storage; when spilling stops, the query often runs more than twice as fast, so it costs less.
- **No spilling → try a smaller size.** A size up roughly halves the runtime at double the rate: the same cost, only faster.
- **Many concurrent queries queuing → multi-cluster warehouse** (scale out), not a bigger size.
- One warehouse per workload (dbt, BI, ad hoc) so they do not slow each other and costs stay visible.
- Guardrails: `auto_suspend = 60`, `auto_resume = true`, `statement_timeout_in_seconds` to stop runaway queries, and a resource monitor on the credit quota.

## 6. Table design, when query changes are not enough

| Feature | Use when | Keep in mind |
|---|---|---|
| natural load order | data arrives in date order and is already well clustered | free |
| clustering key | a very large table is always filtered on the same columns and prunes poorly | automatic clustering costs credits |
| search optimization | point lookups on high-cardinality columns | Enterprise edition; storage and maintenance cost |
| materialized views | the same expensive aggregation on one table is queried often | Enterprise edition; maintenance cost |
| incremental models | a model recomputes its full history on every run | process only new or changed rows |
| typed columns instead of `variant` | `variant` fields are filtered or joined often | extracted columns prune and join well |

Multi-cluster warehouses, search optimization, materialized views and the query acceleration service all require Enterprise edition or higher.
