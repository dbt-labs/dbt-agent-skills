# Writing Context Back

How to write collected context to the project after conducting interviews.

## Output Targets

### 1. Model and Column YAML Descriptions (always available)

This is the primary and always-available output target. Write `description` fields directly into the model's existing properties YAML file.

**Where to write:**
- Find the existing `.yml` or `.yaml` properties file where the model is already defined
- If no properties file exists for the model, create one colocated with the SQL file (e.g., `models/marts/_marts.yml`)
- Never create a separate file when the model is already defined in an existing properties file

**How to write good descriptions:**

Follow the [writing-documentation](../../using-dbt-for-analytics-engineering/references/writing-documentation.md) guidelines. The key principle: **describe why, not just what.**

**Table-level descriptions must include:**
1. **Grain** — one row per what?
2. **Purpose** — what business process does this represent?
3. **Key filters or constraints** — what's included/excluded?
4. **Edge cases** — what would surprise a new team member?

**Column-level descriptions must include:**
1. **Business meaning** — not just restating the column name
2. **Uniqueness** — is it a primary key? Is it globally unique?
3. **Known gotchas** — NULLs, duplicates, misleading values
4. **Calculation** (if derived) — brief formula and what's included/excluded

### Good vs Bad Examples

**Bad — restates the column name:**
```yaml
models:
  - name: fct_orders
    description: A fact table for orders
    columns:
      - name: order_id
        description: The ID of the order
      - name: revenue
        description: The revenue amount
```

**Good — contains institutional knowledge:**
```yaml
models:
  - name: fct_orders
    description: >
      Completed customer orders, one row per order. Only includes orders
      with status = 'completed'. Cancelled, pending, and refunded orders
      are in stg_orders. Revenue columns here are always net of refunds
      and discounts.
    columns:
      - name: order_id
        description: >
          Primary key. Globally unique across all order types. Assigned at
          checkout — draft orders do not have an order_id.
      - name: revenue
        description: >
          Net revenue: gross amount minus refunds and discounts, pre-tax.
          For post-tax revenue, use order_total. For gross revenue before
          any adjustments, use gross_amount in stg_orders.
      - name: account_id
        description: >
          Customer account ID from billing. NOT globally unique — 136
          records share value '1' due to legacy assignment. Use
          account_identifier (prefixed 'act_') for cross-system joins.
```

### Preserving Existing Content

Before writing, always read the existing YAML file. Rules:
- **Never overwrite** an existing description unless the user explicitly confirms the replacement
- **Augment** sparse descriptions — add grain, gotchas, edge cases to descriptions that only restate the name
- **Preserve** all other YAML properties (tests, tags, meta, etc.) — only touch description fields
- **Maintain formatting** — match the indentation style and quoting style of the existing file

### Validation

After writing, run `dbt parse` (or `fusion parse`) to confirm the YAML is syntactically valid:

```bash
dbt parse
```

If parsing fails, read the error, fix the YAML formatting issue, and re-validate.

---

### 2. Project-Level Context

For context that applies broadly across many models — business glossaries, organizational knowledge, cross-cutting rules — write to a project-level location.

**Where to write:**
- A dedicated properties file at the project root: `models/_project_context.yml`
- Or as comments/documentation in `dbt_project.yml`
- Or as a separate documentation block using dbt's `docs` feature

**What goes here (not in model-level descriptions):**
- Business term glossary ("revenue always means net of discounts in this project")
- Organization-wide rules ("always filter out test accounts with is_test = true")
- Cross-model routing ("for customer metrics, use dim_customers, not stg_customers")
- Incident history ("data was stale 2/27-3/16/2026 due to Iceberg corruption")
- Synonym tables ("sales = revenue = income, but bookings is different")

**Example format:**
```yaml
# models/_project_context.yml
# This file contains project-level business context for AI agents and team members.
# It is not processed by dbt directly but serves as a reference for documentation
# and agent context retrieval.

version: 2

docs:
  - name: project_business_context
    description: >
      ## Business Glossary

      **Revenue:** Always means net revenue (gross - refunds - discounts),
      pre-tax. Use fct_orders.subtotal. Never use order_total (includes tax).

      **Active customer:** Customer with at least one completed order in
      the last 90 days. Canonical source: dim_customers.is_active.

      **WAP (Weekly Active Projects):** Distinct count of project_ids with
      a completed (well-formed, both start and end event) invocation in a
      7-day window. Mandated by leadership to match Core's definition.

      ## Known Data Quality Issues

      - account_id is NOT globally unique (136 dupes for value '1').
        Use account_identifier for joins.
      - VSCE events have no event_id (always NULL). Use surrogate key
        from timestamps.

      ## Cross-Model Routing

      - For revenue reporting: use fct_orders (not stg_orders)
      - For customer metrics: use dim_customers (not stg_customers)
      - fct_opportunities vs fct_salesforce_goals: market_segment logic
        differs. Use fct_opportunities for pipeline, fct_salesforce_goals
        for targets.
```

---

### 3. Remote Context Store **[not yet available]**

When the remote context store ships, collected context can be pushed to the organization's central store. This makes context available to:
- All team members across projects
- AI agents in any environment (not just local)
- Non-technical stakeholders via the Catalog UI

**What should go to the remote store:**
- Canonical business definitions (terms that apply org-wide)
- Cross-project knowledge (e.g., "revenue" means the same thing across all projects)
- Context elicited from domain experts that shouldn't be locked in one project
- Gotchas that affect multiple teams

**What should stay local:**
- Model-specific implementation details
- Project-internal conventions
- Temporary notes or work-in-progress context

**How the push flow will work:**

After writing context locally, the agent asks:
> "Would you like to also push this context to your organization's remote context store?"

If yes, the context entry will be pushed with provenance metadata:
- Who contributed it (the user)
- When (timestamp)
- How it was elicited (agent interview, correction during workflow, etc.)
- Review state (draft — requires human review before becoming canonical)

The exact CLI command or API call for pushing is TBD pending the remote store implementation. Placeholder:
```bash
# Future: push context to org-index
# dbt-index ctx push --node model.project.fct_orders --type definition
```
