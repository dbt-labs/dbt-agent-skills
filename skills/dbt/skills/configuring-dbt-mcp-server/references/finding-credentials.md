## How to Find Your Credentials

### Which Token Type Should I Use?

| Use Case | Token Type | Why |
|----------|------------|-----|
| Personal development setup | Personal Access Token (PAT) | Inherits your permissions, works with all APIs including execute_sql |
| Shared team setup | Service Token | Multiple users, controlled permissions, separate from individual accounts |
| Using execute_sql tool | PAT (required) | SQL tools that require `x-dbt-user-id` need a PAT |
| CI/CD or automation | Service Token | System-level access, not tied to a person |

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
