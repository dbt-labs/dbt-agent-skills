### Spark

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
           bool_field: true
           date_field: 2020-01-02
           timestamp_field: 2013-11-03 00:00:00-0
           timestamptz_field: 2013-11-03 00:00:00-0
           int_array_field: 'array(1, 2, 3)'
           map_field: 'map("10", "t", "15", "f", "20", NULL)'
           named_struct_field: 'named_struct("a", 1, "b", 2, "c", 3)'
```
