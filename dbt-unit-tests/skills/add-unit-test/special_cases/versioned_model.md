# Unit testing versioned SQL models

If your model has multiple versions, the default unit test will run on _all_ versions of your model. To specify version(s) of your model to unit test, use `include` or `exclude` for the desired versions in your model versions config:

`models/schema.yml`

```yaml

# my test_is_valid_email_address unit test will run on all versions of my_model
unit_tests:
  - name: test_is_valid_email_address
    model: my_model
    ...
            
# my test_is_valid_email_address unit test will run on ONLY version 2 of my_model
unit_tests:
  - name: test_is_valid_email_address 
    model: my_model 
    versions:
      include: 
        - 2
    ...
            
# my test_is_valid_email_address unit test will run on all versions EXCEPT 1 of my_model
unit_tests:
  - name: test_is_valid_email_address
    model: my_model 
    versions:
      exclude: 
        - 1
    ...

```
