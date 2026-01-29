See below for all the required and optional keys in the YAML definition of unit tests.

`models/schema.yml`

```yml

unit_tests:
  - name: <test-name>  # this is the unique name of the test
    description: <string>  # optional
    model: <model-name>  # required
      versions:  # optional
        include: <list-of-versions-to-include>  # optional
        exclude: <list-of-versions-to-exclude>  # optional
    given:  # required
      - input: <ref_or_source_call>  # optional for seeds
        format: dict | csv | sql  # If not configured, defaults to `dict`
        # either define `rows` inline or name of the `fixture`
        rows: {dictionary} | <string>
        fixture: <fixture-name>  # available option for `sql` or `csv` formats 
      - input: ... # declare additional inputs
    expect:  # required
      format: dict | csv | sql  # If not configured, defaults to `dict`
      # either define `rows` inline or name of the `fixture`
      rows: {dictionary} | <string>
      fixture: <fixture-name>  # available option for `sql` or `csv` formats 
    config:  # optional
      meta: {dictionary}  # optional
      tags: <string> | [<string>]  # optional
      enabled: {boolean}  # optional. v1.9 or higher. If not configured, defaults to `true`
    overrides:  # optional: configuration for the dbt execution environment
      macros:
        is_incremental: true | false
        dbt_utils.current_timestamp: <string>  # example macro name that your model depends upon 
        # ... any other Jinja function
        # ... any other context property
      vars: {dictionary}
      env_vars: {dictionary}
  - name: <test-name> ...  # declare additional unit tests

  ```
