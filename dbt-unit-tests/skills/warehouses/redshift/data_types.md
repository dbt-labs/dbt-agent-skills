### Redshift

Platform-specific data type examples:

```yaml

unit_tests:
  - name: test_my_data_types
    model: fct_data_types
    given:
      - input: ref('stg_data_types')
        rows:
         - int_field: 1
           float_field: 2.0
           str_field: my_string
           str_escaped_field: "my,cool'string"
           date_field: 2020-01-02
           timestamp_field: 2013-11-03 00:00:00-0
           timestamptz_field: 2013-11-03 00:00:00-0
           json_field: '{"bar": "baz", "balance": 7.77, "active": false}'
```

Currently, the `array` data type is not supported for YAML format `dict` inputs. Use the `sql` format instead if you need to mock `array` inputs or outputs.
