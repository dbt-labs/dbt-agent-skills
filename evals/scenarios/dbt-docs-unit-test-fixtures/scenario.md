# dbt Unit Test Fixtures

## Goal
Test whether the LLM can correctly explain how to use fixtures in dbt unit tests.

## Expected Behavior
The LLM should:
1. Explain what fixtures are in dbt unit testing context
2. Show how to define fixture data using the `rows` or `fixture` approach
3. Provide a concrete YAML example with mock input data
4. Mention that fixtures define expected inputs for refs/sources

## Evaluation Criteria
- **Correct**: Shows valid dbt unit test YAML with fixture syntax
- **Accurate**: Information matches current dbt documentation
- **Complete**: Covers both inline rows and external fixture files
