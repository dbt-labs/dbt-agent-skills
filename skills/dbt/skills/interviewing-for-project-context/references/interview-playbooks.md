# Interview Playbooks

Scenario-specific question sets for collecting business context from users. Each playbook includes when to use it, what questions to ask, what to listen for, and how to structure the output.

**General principles:**
- Ask 2-3 related questions per round, capture answers, then move on
- Show the user what you found in gap analysis before asking — they need to see the scope
- Validate your understanding by reading back the context you plan to write
- Do not ask questions you can answer from the manifest or schema — only ask about things that require human knowledge

## Playbook 1: New Project Onboarding

**Trigger:** First time working with a project, or user asks for help documenting their project from scratch.

### Questions

**Domain and purpose:**
- "What business domain does this project cover? (e.g., e-commerce orders, SaaS subscriptions, marketing attribution)"
- "What are the 3-5 most important tables in this project — the ones that stakeholders actually look at?"
- "What business decisions does this data support?"

**Key entities:**
- "What are the core entities? (e.g., customers, orders, products, accounts)"
- "Is there a canonical table for each entity, or are there multiple versions?" (looking for the fct_opportunities vs fct_salesforce_goals problem)

**Team and ownership:**
- "Who are the main consumers of this data? Which teams or dashboards depend on it?"
- "Are there models owned by different teams that overlap in what they represent?"

### What to listen for
- Terms the user defines carefully ("revenue here means...") — these are high-value context
- Hesitations or qualifications ("well, it depends on...") — these signal ambiguity worth documenting
- References to other systems ("that comes from Salesforce") — these clarify data lineage

### Output format
Write project-level context summarizing the domain, key entities, and important tables. Write model-level descriptions for the top 3-5 tables identified.

---

## Playbook 2: Ambiguous Business Terms

**Trigger:** Gap analysis finds models or metrics with overlapping names (e.g., multiple "revenue" columns), or user mentions that terms mean different things to different teams.

### Questions

**Definition disambiguation:**
- "When someone says '[term]' in this project, what exactly do they mean?"
- "Does '[term]' mean the same thing in `[model_a]` and `[model_b]`?"
- "Is there a canonical definition, or do different teams define it differently?"

**Inclusion/exclusion criteria:**
- "What's included in `[metric]`? What's excluded?"
- "Are there filters that must always be applied? (e.g., 'always exclude test orders', 'only status=completed')"

**Synonyms and aliases:**
- "What other words do people use for this concept? (e.g., 'sales', 'income', 'bookings' for revenue)"
- "Do different departments call this something different?"

### What to listen for
- Contradictions ("well, Finance says X but Marketing uses Y") — document both definitions and which context each applies in
- Mandatory filters ("you always have to...") — these prevent common agent errors
- Historical context ("we changed this in Q3 because...") — explains why current state may look confusing

### Output format
Write descriptions that explicitly state the definition used in each model. For project-level terms, write a glossary entry. Always include what the term does NOT mean when it's commonly confused.

Example output:
```yaml
columns:
  - name: revenue
    description: >
      Net revenue after refunds and discounts, pre-tax. This is NOT gross
      revenue — use gross_revenue for that. When someone says "revenue"
      without qualification, this is the canonical column.
```

---

## Playbook 3: Data Quality Gotchas

**Trigger:** Gap analysis finds columns with ID/key suffixes lacking descriptions, or user mentions data quality issues during other interviews.

### Questions

**Identity and uniqueness:**
- "Is `[column_name]` globally unique, or scoped to something?"
- "Can this column be NULL? Under what circumstances?"
- "Are there known duplicate or misleading values?" (the account_id = '1' problem)

**NULL patterns:**
- "Are there columns that are always NULL for certain record types?" (the VSCE event_id problem)
- "What does NULL mean in `[column]` — missing data, not applicable, or something else?"

**Deduplication:**
- "How should records in `[model]` be deduplicated? Is there a natural primary key?"
- "If there's no unique ID, what combination of columns forms a surrogate key?"

**Temporal issues:**
- "Has there been a data incident that affected this data in a specific time range?"
- "Are there known backfill dates or data gaps?"

### What to listen for
- "That's not unique" or "you can't join on that" — critical join safety context
- "It's always NULL for..." — schema inspection alone cannot reveal this
- "We had an incident..." — temporal data quality context
- Workarounds ("we use a surrogate key from...") — document the approved pattern

### Output format
Write column descriptions that explicitly call out uniqueness, NULL semantics, and known edge cases. Use strong warning language for dangerous columns.

Example output:
```yaml
columns:
  - name: account_id
    description: >
      Customer account ID from billing system. WARNING: NOT globally unique.
      136 records share value '1' due to legacy ID assignment. Use
      account_identifier (prefixed 'act_') for cross-system joins.
  - name: event_id
    description: >
      Event identifier. Always NULL for VSCE extension events — these events
      were never assigned IDs. Use the surrogate key (event_timestamps_sk)
      composed of received_at, sent_at, original_timestamp, and uuid_ts.
```

---

## Playbook 4: Metric Definitions

**Trigger:** Gap analysis finds semantic layer metrics without descriptions, or models with calculated columns like `total_revenue`, `active_users`, `churn_rate`.

### Questions

**Formula and logic:**
- "How is `[metric]` calculated? What's the formula?"
- "What table and column is the source of truth for this metric?"
- "Is this gross or net? Pre-tax or post-tax? Are credits/refunds included?"

**Required filters and constraints:**
- "Are there filters that must always be applied?" (e.g., status='completed', is_test=false)
- "Does this metric apply to a specific time grain or cohort?"

**Business mandates:**
- "Was this definition mandated by someone specific? (CEO, Finance, a specific stakeholder)"
- "Is there a documented standard or RFC for this definition?"

**Edge cases:**
- "What happens at the boundaries? (e.g., partial periods, refunds, plan changes)"
- "Are there known discrepancies between this metric and similar ones in other tables?"

### What to listen for
- "Tristan mandated..." or "Finance requires..." — authority behind the definition
- "It doesn't match because..." — known discrepancies worth documenting
- Percentage losses or trade-offs ("we lose ~2% from panics") — these inform accuracy expectations
- References to issues or RFCs — link these in the description

### Output format
Write metric descriptions that include the formula, required filters, authority/rationale, and known edge cases.

---

## Playbook 5: Cross-Model Inconsistencies

**Trigger:** Gap analysis finds the same column name across multiple models with different or missing descriptions, or user mentions tables that "should match but don't."

### Questions

**Identifying the canonical source:**
- "Which of these tables is the source of truth for `[concept]`?"
- "Should `[model_a]` and `[model_b]` produce the same numbers? If not, why?"
- "When stakeholders ask about `[concept]`, which table should they use?"

**Understanding the differences:**
- "What causes the discrepancy between these tables?"
- "Is one table a subset of the other? Different grain? Different filters?"
- "Is this a known issue or intentional?"

**Resolution path:**
- "Is there a plan to consolidate these, or will they remain separate?"
- "Who should someone ask if they see a discrepancy?"

### What to listen for
- "Use this one for X, that one for Y" — document the routing rule
- "They should match but..." — known bug or design debt worth flagging
- "Different grain" — the tables serve different purposes despite similar names

### Output format
Write descriptions on each model that clearly state its purpose relative to the other, which use case it serves, and who to contact for discrepancies.
