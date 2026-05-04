---
name: mapping-dbt-cloud-job-dag
description: Builds a dependency graph (DAG) of dbt Cloud jobs from the Admin API using the dbt Platform CLI (dbtp), including cross-project job-completion triggers. Starts by asking the user for account scope, project IDs, and whether to include all jobs or only completion-linked jobs. Use when mapping job orchestration, documenting run-after relationships, auditing chained jobs, or explaining metadata gaps versus model-level lineage.
user-invocable: false
allowed-tools: "Read, Bash(dbtp *, jq *, python3 *)"
metadata:
  author: dbt-labs
---

# Map dbt Cloud jobs as a DAG

## Context

dbt Cloud exposes **model** lineage (DAG of models) separately from **job** orchestration. Job-to-job dependencies—especially **run when another job completes**—appear on the job definition as `job_completion_trigger_condition`, not in model DAG metadata. This skill produces a **job DAG** from Admin API data via [`dbtp`](https://github.com/dbt-labs/dbt-rust-sdk) (dbt Platform CLI).

## What this captures vs. what it does not

| Captured | Not inferred from this API alone |
|----------|-----------------------------------|
| Edges from **job completion** triggers (`job_completion_trigger_condition`) | Implicit ordering from identical cron schedules |
| Job identity: `id`, `name`, `project_id`, `account_id`, `environment_id` | External orchestrators (Airflow, CI) calling the API |
| Optional node metadata: `execute_steps`, `settings.target_name`, `deactivated`, `triggers` | Model-level lineage (use skill `creating-mermaid-dbt-dag` or MCP lineage tools) |

## Prerequisites

### Install `dbtp` (dbt Platform CLI)

This workflow uses the **`dbtp`** command from the **[dbt Rust SDK](https://github.com/dbt-labs/dbt-rust-sdk)** repo (`dbt-labs/dbt-rust-sdk` on GitHub). The binary name is **`dbtp`** (easy to mistype as `dbtfp`). There is no separate “dbt-rusk-sdk”—that name is a typo for **Rust**.

1. Install a [Rust toolchain](https://rustup.rs/) if needed.
2. Follow the **dbt-rust-sdk** README for the current install path. Typical options:
   - `cargo install dbtp` **if** the crate is published to crates.io as documented there, or
   - Clone the repo and `cargo install --path <path-to-dbtp-crate>` as the README specifies.
3. Ensure the install directory is on `PATH` (often `~/.cargo/bin`). Verify with `dbtp --version`.

If `dbtp` is missing in the agent environment, tell the user to install it from dbt-rust-sdk before running list/get commands.

### API access

- Env vars (or flags): `DBT_TOKEN`, `DBT_ACCOUNT_ID`, and if not `cloud.getdbt.com`, `DBT_HOST` (e.g. `https://your-account.region.dbt.com`)
- Prefer the **least-privileged** token that can read jobs and projects for this workflow. In dbt Cloud permission sets, **Job Admin** or **Job Runner** (or equivalent account-role scopes that include listing and reading job definitions) is often sufficient; you do **not** need blanket “full Admin API” access unless your organization ties job reads to a broader role. Confirm against [dbt Cloud API permissions](https://docs.getdbt.com/docs/dbt-cloud-apis/overview) for your plan.

Do not paste secrets into chat or commit them. Use `.env` or the agent runtime secret store.

## Workflow

### 1. Ask what they want (start here)

For **general / multi-user** use, do **not** assume account or project IDs from the workspace alone. **Ask first**, then map answers to a mode in section **2**.

Prompt for:

1. **Outcome:** Should the diagram include **every** job in scope, **only jobs linked** by “run when another job completes,” or **one/more focus projects** plus **downstream** jobs in other projects that chain off them?
2. **Account & host:** How will they authenticate—`DBT_TOKEN`, `DBT_ACCOUNT_ID`, and `DBT_HOST` (if not the default cloud URL)? Tell them to use `.env`, IDE secrets, or CI variables; **never** ask them to paste tokens into chat.
3. **Projects:** If the scope is not whole-account, which **numeric `project_id`** values? (From dbt Cloud URLs like `/projects/<id>/…` or Project settings.)

Offer modes **1–5** from the table below when it helps them choose. Only after scope is clear should you run `dbtp` or `export_job_dag.py`.

### 2. Confirm scope — pick one mode

Pick **one** mode (the export script mirrors these with `--account`, `--project-id`, `--connected-only`, and `--expand-downstream`).

| Mode | Scope | Diagram / JSON contents |
|------|--------|-------------------------|
| **1. Whole account — all jobs** | Every active job in the account (`jobs list` without `--project-id`). | **Warning:** Large accounts produce huge graphs; the `.mmd` may be slow or unreadable in Mermaid Live and requires many `jobs get` calls. |
| **2. Whole account — connected only** | Same listing as (1), then **keep only jobs that appear on at least one** completion-trigger edge (source or target). Isolated jobs are omitted. | Much smaller when few jobs chain via “run when another job completes.” |
| **3. Listed projects — all jobs** | User supplies one or more `project_id`s; include **every** job in those projects. | Bounded by chosen projects; still includes jobs with **no** completion-trigger edges. |
| **4. Listed projects — connected only** | Same as (3), then drop jobs not incident to any completion-trigger edge **within the induced subgraph** (endpoints only). | Good default when the user cares only about orchestration links. |
| **5. Focus project(s) + cross-project downstream** | User picks **one** (or more) **focus** project(s): include **all** jobs from those projects, **plus** jobs in **other** projects that **completion-trigger from** any job reachable from the focus set (transitive downstream across projects). Does **not** pull in unrelated jobs from other projects. | Surfaces interface points without loading whole-account job lists into the diagram. **Note:** discovering downstream jobs still requires listing/fetching jobs outside the focus projects (the script batches this sensibly); warn the user if the account is huge. |

**Script mapping:** `export_job_dag.py --account` (modes 1–2); `--project-id …` repeated (modes 3–4); same plus `--expand-downstream` (mode 5). Add `--connected-only` for modes 2 and 4.

### 3. List jobs (paginated)

`jobs list` returns job summaries **without** `job_completion_trigger_condition`. Use it for **full job IDs**, names, and pagination.

Account-wide:

```bash
dbtp jobs list --account-id "$DBT_ACCOUNT_ID" -o json --limit 100 --offset 0
```

Single project (repeat per project when not doing account-wide):

```bash
dbtp jobs list --account-id "$DBT_ACCOUNT_ID" --project-id 123456 -o json --limit 100 --offset 0
```

Repeat with `--offset 100`, `200`, … until `extra.pagination.count` is `0` or you have reached `extra.pagination.total_count`.

From each response, collect every `data[].id` (and keep `name`, `project_id`, `environment_id`, `deactivated` for node labels).

Collect the distinct set of `project_id` values for subgraph titles.

### 3b. Resolve project names (subgraph titles)

For **each** distinct `project_id` in scope:

```bash
dbtp projects get --account-id "$DBT_ACCOUNT_ID" --id <PROJECT_ID> -o json
```

Use `data.name` as the project display name. Subgraph title format (see deliverables): `<name> | <project_id>`. If `name` is missing, fall back to `Project | <project_id>`.

**Sanitize** names before putting them inside Mermaid double-quoted titles or node labels (see deliverables). Do not rely on backslash escaping alone—remove problematic characters.

### 4. Fetch full definition per job

For each job id from step 2:

```bash
dbtp jobs get --account-id "$DBT_ACCOUNT_ID" --id <JOB_ID> -o json
```

Run requests in parallel if the environment allows (e.g. `xargs -P 8`) to reduce wall time.

### 5. Extract edges

For each **child** job (the job whose definition you fetched):

1. Read `data.job_completion_trigger_condition` if present.
2. Typical shape:

```json
"job_completion_trigger_condition": {
  "condition": {
    "job_id": 83771,
    "project_id": 89074,
    "statuses": [10]
  }
}
```

3. Add a directed edge **upstream → child**:

- **From** node `(project_id: condition.project_id, job_id: condition.job_id)` — the prerequisite job  
- **To** node `(project_id: child.project_id, job_id: child.id)` — the job you fetched  

`statuses` are numeric run outcomes (commonly `10` = success). Preserve them on the edge label or in edge metadata.

4. If the upstream job id is **outside** the collected set (deleted job or wrong scope), still record the edge and mark `upstream_missing_in_scope: true` on that edge.

5. Jobs with **no** `job_completion_trigger_condition` are **sources** in the job-DAG sense (no upstream edges from this mechanism); they still may run on schedule or webhooks.

### 6. Deliverables

**Coverage** depends on the scope mode from step **2**:

- **All-jobs modes (1 and 3):** Include **every job in scope** in the diagram and in `nodes`, including jobs with **no** completion-trigger edges (show them inside the correct project subgraph).
- **Connected-only modes (2 and 4):** Include **only jobs that lie on at least one** completion-trigger edge; omit isolated jobs from both JSON `nodes` and the Mermaid diagram.
- **Focus + downstream (5):** Include every job in the focus project(s) **plus** downstream jobs pulled in from other projects as defined in the table; subgraphs appear only for projects that still have ≥1 node after filtering.

Provide both:

**A. Structured graph (JSON)** — suitable for docs or tooling. One entry per job in scope; edges only where `job_completion_trigger_condition` exists:

```json
{
  "nodes": [
    {
      "job_id": 83771,
      "project_id": 89074,
      "name": "Nightly Build",
      "environment_id": 85030,
      "deactivated": false
    }
  ],
  "edges": [
    {
      "from": { "job_id": 83771, "project_id": 89074 },
      "to": { "job_id": 876837, "project_id": 323716 },
      "trigger": "job_completion",
      "statuses": [10]
    }
  ],
  "notes": [
    "Edges reflect job_completion_trigger_condition only."
  ]
}
```

**B. Mermaid diagram (`flowchart`)** — prefer **[Mermaid Live](https://mermaid.live)** with the **ELK** renderer, subgraph styling, and labeled cross-project edges (matches how dbt Cloud lineage reads visually).

| Rule | Detail |
|------|--------|
| **Sanitized labels** | Same cleanup on subgraph titles and job labels: remove `"`, `'`, `` ` ``, `#`; replace `[` / `]` with `(` / `)`; strip `<`, `>`, `&`, `*`; collapse whitespace. |
| **Init directive** | Start with `%%{init: …}%%`. Defaults that work well in Mermaid Live: `"defaultRenderer": "elk"`, `"htmlLabels": true`, `"nodeSpacing": 40`, `"rankSpacing": 25`, `"padding": 12`, `"useMaxWidth": false`. Fall back to `"dagre"` if ELK errors. |
| **Top-level direction** | `flowchart LR`. |
| **Nodes** | One node per job: visible **name ` \| ` job_id**; id `job_<job_id>`. |
| **Subgraph titles** | One subgraph per `project_id`: **name ` \| ` project_id** after sanitization (step **3b**). |
| **Subgraph order** | Project-level topological sort so downstream projects are declared **after** upstream donors. |
| **Order inside subgraph** | `direction TB`. Put **cross-project trigger sources** first, then a **topological walk** of **same-project** completion edges whose upstream is **not** already listed as a cross-project source, then remaining incident jobs, then all other jobs (ascending `job_id`). Do **not** add fake `~~~` chains unless the user explicitly wants layout-only spines. |
| **`classDef` / `class`** | After `flowchart LR`, define one `classDef` per project (stroke + fill). Typical two-project palette: **projectA** teal (`stroke:#2dd4bf,fill:#f0fdfa`), **projectB** purple (`stroke:#a78bfa,fill:#f5f3ff`). For three or more projects, add **projectC**, **projectD** (e.g. orange / sky) and rotate. Apply with `class proj_<id>,job_<id>,… projectX` — dedupe ids so each node appears once. |
| **Edges** | Completion triggers only. Same-project: `job_a --> job_b`. Cross-project: labeled dashed arrow, e.g. `job_a -. "triggers downstream project job" .-> job_b` (adjust text if the user prefers). |

Example (pattern only):

```mermaid
%%{init: {"flowchart": {"defaultRenderer": "elk","htmlLabels": true,"nodeSpacing": 40,"rankSpacing": 25,"padding": 12,"useMaxWidth": false}}}%%
flowchart LR
  classDef projectA stroke:#2dd4bf,fill:#f0fdfa
  classDef projectB stroke:#a78bfa,fill:#f5f3ff
  subgraph proj_1["Sandbox | 1"]
    direction TB
    job_10["Alpha | 10"]
    job_11["Beta | 11"]
  end
  subgraph proj_2["Downstream | 2"]
    direction TB
    job_20["Gamma | 20"]
  end
  job_10 --> job_11
  job_10 -. "triggers downstream project job" .-> job_20
  class proj_1,job_10,job_11 projectA
  class proj_2,job_20 projectB
```

**C. `.mmd` file (optional)** — For [Mermaid Live](https://mermaid.live) or CLI renderers: **UTF-8** plain text (no markdown fence). A committed **shape reference** lives at [`job-dag-example.mmd`](./job-dag-example.mmd) (fictional ids); real exports go under **`exports/`**, which is **gitignored**.

From the `dbt-agent-skills` repo root, each run defaults to **`exports/job-dag-export-<timestamp>.mmd`** (local time `YYYYMMDD-HHMMSS`). Examples by scope mode:

```bash
# Mode 1 — whole account, all jobs (large; may be unreadable)
python3 skills/dbt-extras/skills/mapping-dbt-cloud-job-dag/scripts/export_job_dag.py --account

# Mode 2 — whole account, only jobs on completion-trigger edges
python3 skills/dbt-extras/skills/mapping-dbt-cloud-job-dag/scripts/export_job_dag.py --account --connected-only

# Mode 3 — listed projects, all jobs
python3 skills/dbt-extras/skills/mapping-dbt-cloud-job-dag/scripts/export_job_dag.py \
  --project-id 111 --project-id 222

# Mode 4 — listed projects, connected only
python3 skills/dbt-extras/skills/mapping-dbt-cloud-job-dag/scripts/export_job_dag.py \
  --project-id 111 --project-id 222 --connected-only

# Mode 5 — focus project(s): all jobs there + downstream jobs in other projects
python3 skills/dbt-extras/skills/mapping-dbt-cloud-job-dag/scripts/export_job_dag.py \
  --project-id 111 --expand-downstream
```

Optional: `--renderer elk`, `--cross-project-label "…"`. Pin output path with `-o file.mmd` (no timestamp) or `-o /tmp` (timestamped file inside `/tmp`).

**Snapshots:** Each fetch-mode run writes **`job-dag-export-<timestamp>.json`** beside the `.mmd` (same stem), containing full **`jobs get`** payloads plus `project_names` and capture metadata. **`--no-snapshot`** skips writing it. To change **`--renderer`** / **`--cross-project-label`** / **`--connected-only`** without repeating slow API calls, re-run with **`--from-snapshot path/to/job-dag-export-….json`** (no `--account` / `--project-id` / `--expand-downstream`). That path needs no `dbtp` or `DBT_*` env.

Long runs (especially whole-account) print **progress on stderr** (`[job-dag-export]` lines: project/job counts, fetch milestones). Use **`--quiet`** to suppress those lines; the written **output path** is still printed on stderr at the end.

(`DBT_TOKEN`, `DBT_ACCOUNT_ID`, `DBT_HOST` must be set for **fetch** mode; **`dbtp`** from **dbt-rust-sdk** on `PATH`; optional `DBTP_PATH`.)

If the graph is large, prefer modes **2**, **4**, or **5**, or add prose **after** the diagram unless the user asks for a filtered view.

## jq sketch (optional)

After saving list payloads to files or piping, you can collect ids:

```bash
jq -r '.data[].id' list_page.json
```

Combine `jobs get` outputs and parse `job_completion_trigger_condition` similarly—exact jq depends on whether outputs are merged into one array or one file per job.

## Troubleshooting

| Issue | Action |
|-------|--------|
| `dbtp` / `command not found` | Install **`dbtp`** from [dbt-rust-sdk](https://github.com/dbt-labs/dbt-rust-sdk) (see Prerequisites); confirm `PATH` includes Cargo bin or symlink |
| `401` / auth errors | Verify `DBT_TOKEN` and host; confirm token has job/project read (e.g. Job Admin / Job Runner–class scopes), not necessarily full admin |
| Slow **mode 5** / huge account | Downstream discovery lists non-focus projects and one `jobs get` per foreign job; acceptable for small accounts—otherwise narrow focus projects or use modes 3–4 |
| Empty `data` on list | Check `--project-id`, `DBT_ACCOUNT_ID`, and `--state active` |
| No edges | Account may only use schedules/webhooks—confirm in UI **Triggers → Run when another job completes** |
| Rate limits | Reduce parallel `jobs get`; backoff |

## Related

- **Model DAG / lineage**: skill `creating-mermaid-dbt-dag`
- **Failed runs**: skill `troubleshooting-dbt-job-errors`
