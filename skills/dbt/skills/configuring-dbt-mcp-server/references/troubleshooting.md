## Troubleshooting

### "uvx not found" or "spawn uvx ENOENT"
Find full path and use it in config:
```bash
# macOS/Linux
which uvx
# Use output like: /opt/homebrew/bin/uvx

# Windows
where uvx
```

Update config:
```json
{
  "command": "/opt/homebrew/bin/uvx",
  "args": ["dbt-mcp"]
}
```

### "Could not connect to MCP server"
1. Check `uvx` is installed: `uvx --version`
2. Verify paths exist: `ls $DBT_PROJECT_DIR/dbt_project.yml`
3. Check dbt works: `$DBT_PATH --version`

### OAuth Not Working
Only accounts with static subdomains (e.g., `abc123.us1.dbt.com`) support OAuth. Check your Access URLs in dbt platform settings.

### Remote Server Returns 401/403
- Verify token has Semantic Layer and Developer permissions
- For `execute_sql`: Use personal access token, not service token
- Check environment ID is correct (from Orchestration page)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using npm/npx instead of uvx | The package is `dbt-mcp` via `uvx`, not npm |
| Wrong env var names (DBT_CLOUD_*) | Use `DBT_TOKEN`, `DBT_PROD_ENV_ID`, etc. |
| Using `mcpServers` in VS Code | VS Code uses `servers` key in mcp.json |
| Service token for execute_sql | Use personal access token for SQL tools |
| Windows paths in WSL | Use Linux paths (`/home/...`) not Windows |
| Local user settings in WSL | Must use Remote settings in VS Code |
| Missing `uv` installation | Install uv first: https://docs.astral.sh/uv/ |
