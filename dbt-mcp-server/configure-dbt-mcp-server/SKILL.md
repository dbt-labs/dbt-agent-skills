---
name: configure-dbt-mcp-server
description: Use when user wants to set up, configure, or troubleshoot the dbt MCP server for AI tools like Claude Desktop, Claude Code, Cursor, or VS Code
---

# Configure dbt MCP Server

## Overview

The dbt MCP server connects AI tools to dbt's CLI, Semantic Layer, Discovery API, and Admin API. This skill guides users through setup with the correct configuration for their use case.

## Decision Flow

```dot
digraph setup_flow {
    rankdir=TB;
    node [shape=box];

    start [label="User wants dbt MCP" shape=ellipse];
    q1 [label="Local or Remote?" shape=diamond];
    local [label="Local Server\n(uvx dbt-mcp)"];
    remote [label="Remote Server\n(HTTP endpoint)"];
    q2 [label="Which client?" shape=diamond];
    claude_desktop [label="Claude Desktop"];
    claude_code [label="Claude Code"];
    cursor [label="Cursor"];
    vscode [label="VS Code"];
    config [label="Generate config\n+ test setup"];

    start -> q1;
    q1 -> local [label="dev workflows\nCLI access needed"];
    q1 -> remote [label="consumption only\nno local install"];
    local -> q2;
    remote -> q2;
    q2 -> claude_desktop;
    q2 -> claude_code;
    q2 -> cursor;
    q2 -> vscode;
    claude_desktop -> config;
    claude_code -> config;
    cursor -> config;
    vscode -> config;
}
```

## Questions to Ask

### 1. Server Type
**Ask:** "Do you want to use the **local** or **remote** dbt MCP server?"

| Local Server | Remote Server |
|--------------|---------------|
| Runs on your machine via `uvx` | Connects via HTTP to dbt platform |
| Best for development (authoring models, tests, docs) | Best for consumption (querying metrics, exploring metadata) |
| Supports dbt CLI commands | No CLI commands (run, build, test) |
| Works without dbt platform account | Requires dbt platform account |
| No credit consumption | Consumes dbt Copilot credits |

### 2. MCP Client
**Ask:** "Which MCP client are you using?"
- Claude Desktop
- Claude Code (CLI)
- Cursor
- VS Code

### 3. Use Case (Local Server Only)
**Ask:** "What's your use case?"

| CLI Only | Platform Only | Platform + CLI |
|----------|---------------|----------------|
| dbt Core/Fusion users | dbt Cloud without local project | Full access to both |
| No platform account needed | OAuth or token auth | Requires paths + credentials |

### 4. Tools to Enable
**Ask:** "Which tools do you want enabled?" (show defaults)

| Tool Category | Default | Environment Variable |
|---------------|---------|---------------------|
| dbt CLI (run, build, test, compile) | Enabled | `DISABLE_DBT_CLI=true` to disable |
| Semantic Layer (metrics, dimensions) | Enabled | `DISABLE_SEMANTIC_LAYER=true` to disable |
| Discovery API (models, lineage) | Enabled | `DISABLE_DISCOVERY=true` to disable |
| Admin API (jobs, runs) | Enabled | `DISABLE_ADMIN_API=true` to disable |
| SQL (text_to_sql, execute_sql) | **Disabled** | `DISABLE_SQL=false` to enable |
| Codegen (generate models/sources) | **Disabled** | `DISABLE_DBT_CODEGEN=false` to enable |

## Prerequisites

### Local Server
1. **Install `uv`**: https://docs.astral.sh/uv/getting-started/installation/
2. **Have a dbt project** (for CLI commands)
3. **Find paths:**
   - `DBT_PROJECT_DIR`: Folder containing `dbt_project.yml`
     - macOS/Linux: `pwd` from project folder
     - Windows: Full path with forward slashes (e.g., `C:/Users/name/project`)
   - `DBT_PATH`: Path to dbt executable
     - macOS/Linux: `which dbt`
     - Windows: `where dbt`

### Remote Server
1. **dbt Cloud account** with AI features enabled
2. **Production environment ID** (from Orchestration page)
3. **Personal access token** or service token

## How to Find Your Credentials

### Personal Access Token (PAT)

1. Go to **Account Settings** → expand **API tokens** → click **Personal tokens**
2. Click **Create personal access token**
3. Enter a descriptive name and click **Save**
4. **Copy the token immediately** — it won't be shown again

**Notes:**
- Requires a Developer license
- Inherits all permissions from your user account
- Account-scoped: create separate tokens for each dbt account you access
- Rotate regularly for security

### Service Token

Use service tokens for system-level integrations (CI/CD, automation) rather than user-specific access.

1. Go to **Account Settings** → **Service Tokens** (in left sidebar)
2. Click **+ New Token**
3. Select the appropriate permission set for your use case
4. **Save the token immediately** — it won't be shown again

**Permission sets for MCP:**
- **Semantic Layer Only**: For querying metrics only
- **Metadata Only**: For Discovery API access
- **Job Admin**: For Admin API (triggering jobs)
- **Developer**: For broader access

**Notes:**
- Requires Developer license + account admin permissions to create
- Service tokens belong to the account, not a user
- Cannot use service tokens for `execute_sql` — use PAT instead

### Account ID

1. Sign in to dbt Cloud
2. Look at the URL in your browser — the Account ID is the number after `/accounts/`

**Example:** In `https://cloud.getdbt.com/settings/accounts/12345/...`, the Account ID is `12345`

**Alternative:** Go to **Settings** → **Account Settings** and check the URL.

### Environment ID (Production or Development)

1. In dbt Cloud, go to **Deploy** → **Environments**
2. Click on the environment (Production or Development)
3. Look at the URL — the Environment ID is the last number

**URL pattern:** `https://cloud.getdbt.com/deploy/<account_id>/projects/<project_id>/environments/<environment_id>`

**Example:** In `.../environments/98765`, the Environment ID is `98765`

### User ID

1. Go to **Account Settings** → **Team** → **Users**
2. Click on your user profile
3. Look at the URL — the number after `/users/` is your User ID

**Example:** In `https://cloud.getdbt.com/settings/accounts/12345/users/67891`, the User ID is `67891`

## Configuration Templates

### Local Server - CLI Only

```json
{
  "mcpServers": {
    "dbt": {
      "command": "uvx",
      "args": ["dbt-mcp"],
      "env": {
        "DBT_PROJECT_DIR": "/path/to/your/dbt/project",
        "DBT_PATH": "/path/to/dbt"
      }
    }
  }
}
```

### Local Server - Platform + CLI (OAuth)

```json
{
  "mcpServers": {
    "dbt": {
      "command": "uvx",
      "args": ["dbt-mcp"],
      "env": {
        "DBT_HOST": "https://your-subdomain.us1.dbt.com",
        "DBT_PROJECT_DIR": "/path/to/project",
        "DBT_PATH": "/path/to/dbt"
      }
    }
  }
}
```

### Local Server - Platform + CLI (Token Auth)

```json
{
  "mcpServers": {
    "dbt": {
      "command": "uvx",
      "args": ["dbt-mcp"],
      "env": {
        "DBT_HOST": "cloud.getdbt.com",
        "DBT_TOKEN": "your-token",
        "DBT_ACCOUNT_ID": "your-account-id",
        "DBT_PROD_ENV_ID": "your-prod-env-id",
        "DBT_PROJECT_DIR": "/path/to/project",
        "DBT_PATH": "/path/to/dbt"
      }
    }
  }
}
```

### Local Server - Using .env File

```json
{
  "mcpServers": {
    "dbt": {
      "command": "uvx",
      "args": ["--env-file", "/path/to/.env", "dbt-mcp"]
    }
  }
}
```

**.env file contents:**
```
DBT_HOST=cloud.getdbt.com
DBT_TOKEN=your-token
DBT_ACCOUNT_ID=your-account-id
DBT_PROD_ENV_ID=your-prod-env-id
DBT_DEV_ENV_ID=your-dev-env-id
DBT_USER_ID=your-user-id
DBT_PROJECT_DIR=/path/to/project
DBT_PATH=/path/to/dbt
```

### Remote Server

```json
{
  "mcpServers": {
    "dbt": {
      "url": "https://cloud.getdbt.com/api/ai/v1/mcp/",
      "headers": {
        "Authorization": "token your-token",
        "x-dbt-prod-environment-id": "your-prod-env-id"
      }
    }
  }
}
```

**Additional headers for SQL/Fusion tools:**
```json
{
  "headers": {
    "Authorization": "token your-token",
    "x-dbt-prod-environment-id": "your-prod-env-id",
    "x-dbt-dev-environment-id": "your-dev-env-id",
    "x-dbt-user-id": "your-user-id"
  }
}
```

## Client-Specific Setup

### Claude Desktop
1. Click **Claude menu** in system menu bar (not in-app)
2. Select **Settings...**
3. Go to **Developer** tab
4. Click **Edit Config**
5. Add the JSON configuration
6. Save and restart Claude Desktop
7. **Verify:** Look for MCP server indicator in bottom-right of input box

**Config location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Claude Code (CLI)
Run:
```bash
claude mcp add dbt -s user -- uvx dbt-mcp
```

Or edit `~/.claude/settings.json` directly with the JSON config under `mcpServers`.

### Cursor
1. Open **Cursor menu** → **Settings** → **Cursor Settings** → **MCP**
2. Add the JSON configuration
3. Update paths and credentials
4. Save

### VS Code
1. Open **Command Palette** (Cmd/Ctrl + Shift + P)
2. Run **"MCP: Open User Configuration"** (or Workspace for project-specific)
3. Add the JSON configuration (note: VS Code uses `servers` not `mcpServers`):

```json
{
  "servers": {
    "dbt": {
      "command": "uvx",
      "args": ["dbt-mcp"],
      "env": {
        "DBT_PROJECT_DIR": "/path/to/project",
        "DBT_PATH": "/path/to/dbt"
      }
    }
  }
}
```

4. Open **Settings** → **Features** → **Chat** → Enable **MCP**
5. **Verify:** Run **"MCP: List Servers"** from Command Palette

**WSL Users:** Configure in Remote settings, not local user settings:
- Run **"Preferences: Open Remote Settings"** from Command Palette
- Use full Linux paths (e.g., `/home/user/project`, not Windows paths)

## Verification Steps

### Test Local Server Config
```bash
# Set environment variables
export DBT_PROJECT_DIR=/path/to/project
export DBT_PATH=/path/to/dbt

# Run the server
uvx dbt-mcp
```

No errors = successful configuration.

### Test with .env File
```bash
uvx --env-file /path/to/.env dbt-mcp
```

### Verify in Client
After setup, ask the AI:
- "What dbt tools do you have access to?"
- "List my dbt metrics" (if Semantic Layer enabled)
- "Show my dbt models" (if Discovery enabled)

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
