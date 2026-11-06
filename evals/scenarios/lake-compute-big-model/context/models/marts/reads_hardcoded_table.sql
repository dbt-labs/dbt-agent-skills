-- Reads a table dbt doesn't know about (no source() or ref()).
select id, name from RAW_LEGACY.EXPORTS.UNTRACKED_CUSTOMERS
