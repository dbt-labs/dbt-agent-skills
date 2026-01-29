## Another example of unit testing a model

This example creates a new `dim_customers` model with a field `is_valid_email_address` that calculates whether or not the customer’s email is valid: 

`dim_customers.sql`

```sql
with customers as (

    select * from {{ ref('stg_customers') }}

),

accepted_email_domains as (

    select * from {{ ref('top_level_email_domains') }}

),
	
check_valid_emails as (

    select
        customers.customer_id,
        customers.first_name,
        customers.last_name,
        customers.email,
	      coalesce (regexp_like(
            customers.email, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'
        )
        = true
        and accepted_email_domains.tld is not null,
        false) as is_valid_email_address
    from customers
		left join accepted_email_domains
        on customers.email_top_level_domain = lower(accepted_email_domains.tld)

)

select * from check_valid_emails
```

The logic posed in this example can be challenging to validate. You can add a unit test to this model to ensure the `is_valid_email_address` logic captures all known edge cases: emails without `.`, emails without `@`, and emails from invalid domains.

`dbt_project.yml`

```yaml
unit_tests:
  - name: test_is_valid_email_address
    description: "Check my is_valid_email_address logic captures all known edge cases - emails without ., emails without @, and emails from invalid domains."

    # Model
    model: dim_customers

    # Inputs
    given:
      - input: ref('stg_customers')
        rows:
          - {email: cool@example.com,    email_top_level_domain: example.com}
          - {email: cool@unknown.com,    email_top_level_domain: unknown.com}
          - {email: badgmail.com,        email_top_level_domain: gmail.com}
          - {email: missingdot@gmailcom, email_top_level_domain: gmail.com}
      - input: ref('top_level_email_domains')
        rows:
          - {tld: example.com}
          - {tld: gmail.com}

    # Output
    expect:
      rows:
        - {email: cool@example.com,    is_valid_email_address: true}
        - {email: cool@unknown.com,    is_valid_email_address: false}
        - {email: badgmail.com,        is_valid_email_address: false}
        - {email: missingdot@gmailcom, is_valid_email_address: false}

```

# Data `format`s for unit tests

## `dict`

### Inline `dict` example

The `dict` data format is the default if no `format` is defined.

`dict` requires an inline YAML dictionary for `rows`:

`models/schema.yml`

```yaml
unit_tests:
  - name: test_my_model
    model: my_model
    given:
      - input: ref('my_model_a')
        format: dict
        rows:
          - {id: 1, name: gerda}
          - {id: 2, name: michelle}
```

## `csv`

### Inline `csv` example

When using the `csv` format, you can use either an inline CSV string for `rows`:

`models/schema.yml`

```yaml

unit_tests:
  - name: test_my_model
    model: my_model
    given:
      - input: ref('my_model_a')
        format: csv
        rows: |
          id,name
          1,gerda
          2,michelle

```

### Fixture `csv` example

Or, you can provide the name of a CSV file in the `test-paths` location (`tests/fixtures` by default): 

`models/schema.yml`

```yaml

unit_tests:
  - name: test_my_model
    model: my_model
    given:
      - input: ref('my_model_a')
        format: csv
        fixture: my_model_a_fixture

```

`tests/fixtures/my_model_a_fixture.csv`

```csv

id,name
1,gerda
2,michelle

```

## `sql`

When using the `sql` format, you can use either an inline SQL query for `rows`:

### Inline `sql` example

`models/schema.yml`

```yaml

unit_tests:
  - name: test_my_model
    model: my_model
    given:
      - input: ref('my_model_a')
        format: sql
        rows: |
          select 1 as id, 'gerda' as name, null as loaded_at union all
          select 2 as id, 'michelle', null as loaded_at as name

```

### Fixture `sql` example

Or, you can provide the name of a SQL file in the `test-paths` location (`tests/fixtures` by default): 

`models/schema.yml`

```yaml

unit_tests:
  - name: test_my_model
    model: my_model
    given:
      - input: ref('my_model_a')
        format: sql
        fixture: my_model_a_fixture

```

`tests/fixtures/my_model_a_fixture.sql`

```sql

select 1 as id, 'gerda' as name, null as loaded_at union all
select 2 as id, 'michelle', null as loaded_at as name

```

**Notes**
- Contrary to dbt SQL models, Jinja is unsupported within SQL fixtures for unit tests.
- You must supply mock data for _all columns_ when using the `sql` format.
