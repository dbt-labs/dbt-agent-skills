## Unit testing a model that depends on ephemeral model(s)

If you want to unit test a model that depends on an ephemeral model, you must use `format: sql` for that input.

```yml
unit_tests:
  - name: my_unit_test
    model: dim_customers
    given:
      - input: ref('ephemeral_model')
        format: sql
        rows: |
          select 1 as id, 'emily' as name
    expect:
      rows:
        - {id: 1, first_name: emily}
```
