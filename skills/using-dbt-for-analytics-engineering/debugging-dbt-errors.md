# How to debug dbt error messages

## Review logs and artifacts

If you are prompted to fix a bug, start by reviewing the logs and artifacts from the most recent dbt invocation. See `scripts/review_run_results.md` for an example.

- The `logs/dbt.log` file contains all the queries that dbt ran, and additional logging. Recent errors will be at the bottom of the file.
- The `target/run_results.json` file contains each model which ran in the most recent invocation, and whether they succeeded or not. See `scripts/review_run_results` for sample code.
- The `target/compiled` directory contains the rendered model code as a select statement.
- The `target/run` directory contains that rendered code inside of DDL statements such as `CREATE TABLE AS SELECT`.

If the error came from the console, read the error message.

The error messages dbt produces will normally contain the type of error, and the file where the error occurred.

## Classify and resolve the error

dbt project errors can have several root causes:

### Invalid dbt project configuration

These are likely to be YAML or parsing errors:

```bash
error: dbt1013: YAML error: did not find expected key at line 14 column 7, while parsing a block mapping at line 11 column 5
  --> models/anchor_tests.yml:14:7
```

```bash
Encountered an error:
Parsing Error
  Error reading jaffle_shop: anchor_tests.yml - Runtime Error
    Syntax error near line 14
```

These errors can be fixed by updating the impacted files, ensuring they conform to the correct YAML structure.

### Invalid model code

These are likely to be compilation or SQL errors, or a failing unit test:

```bash
error: dbt1005: Found duplicate model 'my_first_model'
  --> models/my_first_model.sql
```

```bash
error: dbt0101: mismatched input 'orders' expecting one of 'SELECT', 'TABLE', '('
  --> models/marts/customers.sql:9:1 (target/compiled/models/marts/customers.sql:9:1)
```

```bash
03:16:39  Failure in unit_test test_does_location_opened_at_trunc_to_date (models/staging/stg_locations.yml)
03:16:39    

actual differs from expected:

@@,location_id,location_name,tax_rate,opened_date
  ,1          ,Vice City    ,0.2     ,2016-09-01 00:00:00
→ ,2          ,San Andreas  ,0.1     ,2079-10-27 00:00:00→2079-10-27 23:59:59.999900
```

These should be fixed by updating the referenced files in the error message. Fix invalid SQL, and ensure that the transformations produce the desired output based on defined tests and documentation.

### Invalid data

Invalid data is detected during execution of a dbt project, e.g. during `dbt build`, `dbt test` or `dbt run`.

```bash
03:29:09  Failure in test accepted_values_customers_customer_type__new__returning (models/marts/customers.yml)
03:29:09    Got 1 result, configured to fail if != 0
03:29:09  
03:29:09    compiled code at target/compiled/jaffle_shop/models/marts/customers.yml/accepted_values_customers_customer_type__new__returning.sql
```

It normally needs to be resolved by transforming the underlying data to match the test's expectations. Perform transformations as early in the DAG as possible, ideally in a staging layer.

Do not remove a test, or modify a test to pass, without explicit permission.

## Check that the error is resolved

After making the necessary project changes, run the most efficient command that will validate the problem is solved.

- `dbt parse` is fast and does not require warehouse resources. It will only identify dbt project misconfigurations. It is implicitly run in all other commands, so only explicitly invoke it if the issue was a project misconfiguration instead of invalid models or data.
- `dbt compile --select broken_model` is relatively fast and cheap to run. It will only identify SQL errors when using the dbt Fusion engine (version 2.0 and above).
- `dbt build --select broken_model` is the most reliable way to ensure that a model and its tests are passing, but will take a while and consume warehouse resources.

When running commands that connect to the warehouse (everything except dbt parse), **ALWAYS** use a `--select` flag to avoid processing the entire dbt project and consuming excessive resources.
