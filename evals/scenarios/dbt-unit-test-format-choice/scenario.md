# dbt Unit Test Format Choice

## Goal
Test whether the LLM can correctly explain when to use different data formats (`dict`, `csv`, `sql`) in dbt unit tests.

## Expected Behavior
The LLM should:
1. Explain that `dict` (inline YAML) is the default format and should be used by default
2. Explain when to use `sql` format:
   - When testing a model that depends on an ephemeral model
   - When unit testing columns with data types not supported by `dict` or `csv`
   - As a fallback when other formats won't work
3. Explain when to use `csv` format:
   - When using fixture files (preferred over `sql` for readability)
   - Fallback to `sql` if column data types aren't supported by `csv`
4. Mention key tradeoffs:
   - `sql` format requires specifying ALL columns (less convenient)
   - `dict` and `csv` allow specifying only a subset of columns
   - `sql` is the most flexible but least readable

## Evaluation Criteria
- **Correct**: Accurately describes when each format is appropriate
- **Complete**: Covers ephemeral model dependency requirement for `sql`
- **Practical**: Gives actionable guidance on format selection
- **Accurate**: Information matches current dbt documentation
