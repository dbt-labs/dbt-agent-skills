# dbt Job Failure Debugging

## Goal
Test whether the LLM can effectively use MCP tools to diagnose a dbt Cloud job failure.

## Expected Behavior
The LLM should:
1. Use the dbt MCP server to list recent job runs
2. Identify the failed run from January 14th
3. Get detailed error information using `get_job_run_error`
4. Classify the error type and investigate appropriately
5. Either find the root cause or document what was checked

## Evaluation Criteria
- **Tool Usage**: Did it use the MCP tools effectively?
- **Systematic**: Did it follow a logical debugging process?
- **Documentation**: Did it document findings appropriately?

## Prerequisites
This scenario requires:
- dbt MCP server running with valid credentials
- Access to a dbt Cloud account with job history
