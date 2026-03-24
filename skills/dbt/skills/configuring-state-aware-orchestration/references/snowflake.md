# Snowflake-Specific Considerations

Use this reference when configuring SAO for Snowflake objects whose metadata timing does not map cleanly to underlying data changes.

## Shared Tables

- For shared tables, Snowflake updates `INFORMATION_SCHEMA.TABLES.LAST_ALTERED` when table data changes.
- In these cases, SAO can usually detect new data without additional freshness configuration.

## Shared Views

- For shared views, including secure views, `INFORMATION_SCHEMA.TABLES.LAST_ALTERED` updates only when the view object itself changes.
- It does not update when the underlying data behind the view changes.
- For shared views, define `loaded_at_field` or `loaded_at_query` so SAO uses a freshness signal tied to data recency.
- dbt can warn about this behavior for standard views, but shared objects may not expose enough metadata to reliably distinguish a shared table from a shared view. Treat shared-view sources as cases that need explicit freshness config.

## Dynamic Tables

- For dynamic tables, `LAST_ALTERED` updates when the dynamic table refresh runs, not when upstream source tables change.
- If precise freshness handling matters, define `loaded_at_query` using `LATEST_DATA_TIMESTAMP` from Snowflake information schema so SAO keys off data recency instead of object-alter timing.
- This is a practical workaround for now and an area where product behavior may improve over time.

## Recommended Pattern

1. Check whether the object metadata you are relying on reflects data arrival or only object-level changes.
2. If metadata timing is not aligned with real freshness expectations, add explicit `loaded_at_field` or `loaded_at_query` configuration.
3. Validate the resulting behavior by comparing source arrival timing, object metadata, and actual SAO skip or rebuild decisions.
