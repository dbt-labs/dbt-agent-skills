## Unit testing incremental models

When configuring your unit test, you can override the output of macros, vars, or environment variables. This enables you to unit test your incremental models in "full refresh" and "incremental" modes.

### Note
Incremental models need to exist in the database first before running unit tests. Use the `--empty` flag to build an empty version of the models to save warehouse spend. You can also optionally select only your incremental models using the `--select` flag.

  ```shell
  dbt run --select "config.materialized:incremental" --empty
  ```

  After running the command, you can then perform a regular `dbt build` for that model and then run your unit test.

When testing an incremental model, the expected output is the __result of the materialization__ (what will be merged/inserted), not the resulting model itself (what the final table will look like after the merge/insert).

For example, say you have an incremental model in your project:

`my_incremental_model.sql`

```sql

{{
    config(
        materialized='incremental'
    )
}}

select * from {{ ref('events') }}
{% if is_incremental() %}
where event_time > (select max(event_time) from {{ this }})
{% endif %}

```

You can define unit tests on `my_incremental_model` to ensure your incremental logic is working as expected:

```yml

unit_tests:
  - name: my_incremental_model_full_refresh_mode
    model: my_incremental_model
    overrides:
      macros:
        # unit test this model in "full refresh" mode
        is_incremental: false 
    given:
      - input: ref('events')
        rows:
          - {event_id: 1, event_time: 2020-01-01}
    expect:
      rows:
        - {event_id: 1, event_time: 2020-01-01}

  - name: my_incremental_model_incremental_mode
    model: my_incremental_model
    overrides:
      macros:
        # unit test this model in "incremental" mode
        is_incremental: true 
    given:
      - input: ref('events')
        rows:
          - {event_id: 1, event_time: 2020-01-01}
          - {event_id: 2, event_time: 2020-01-02}
          - {event_id: 3, event_time: 2020-01-03}
      - input: this 
        # contents of current my_incremental_model
        rows:
          - {event_id: 1, event_time: 2020-01-01}
    expect:
      # what will be inserted/merged into my_incremental_model
      rows:
        - {event_id: 2, event_time: 2020-01-02}
        - {event_id: 3, event_time: 2020-01-03}

```

There is currently no way to unit test whether the dbt framework inserted/merged the records into your existing model correctly, but we're investigating support for this in the future in GitHub issue #8664.
