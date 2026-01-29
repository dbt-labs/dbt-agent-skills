# Caveats for Redshift

## Unit test limitations for Redshift

- Redshift doesn't support unit tests when the SQL in the common table expression (CTE) contains functions such as `LISTAGG`, `MEDIAN`, `PERCENTILE_CONT`, and so on. These functions must be executed against a user-created table. dbt combines given rows to be part of the CTE, which Redshift does not support.

  In order to support this pattern in the future, dbt would need to "materialize" the input fixtures as tables, rather than interpolating them as CTEs. Adding this functionality is proposed in GitHub issue #8499.

- Redshift doesn't support unit tests that rely on sources in a database that differs from the models. Redshift sources need to be in the same database as the models.
