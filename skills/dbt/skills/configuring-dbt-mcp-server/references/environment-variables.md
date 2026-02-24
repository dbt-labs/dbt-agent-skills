## Environment Variable Reference

| Variable | Required For | Description |
|----------|--------------|-------------|
| `DBT_PROJECT_DIR` | CLI commands | Path to folder with `dbt_project.yml` |
| `DBT_PATH` | CLI commands | Path to dbt executable |
| `DBT_HOST` | Platform access | Default: `cloud.getdbt.com` |
| `DBT_TOKEN` | Platform (non-OAuth) | Personal or service token |
| `DBT_ACCOUNT_ID` | Admin API | Your dbt account ID |
| `DBT_PROD_ENV_ID` | Platform access | Production environment ID |
| `DBT_DEV_ENV_ID` | SQL/Fusion tools | Development environment ID |
| `DBT_USER_ID` | SQL/Fusion tools | Your dbt user ID |
| `MULTICELL_ACCOUNT_PREFIX` | Multi-cell accounts | Account prefix (exclude from DBT_HOST) |
| `DBT_CLI_TIMEOUT` | CLI commands | Timeout in seconds (default: 60) |
| `DBT_MCP_LOG_LEVEL` | Debugging | DEBUG, INFO, WARNING, ERROR, CRITICAL |
