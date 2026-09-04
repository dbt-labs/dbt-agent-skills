# Suggesting Business Metrics on Fact Tables

This is the highest-value and highest-risk part of the skill: reading a fact table's actual shape and proposing metrics a business user would recognize — without inventing something the data doesn't actually support, and without adding anything to the LookML without confirmation.

## Ground every suggestion in two things

1. **What the columns actually contain** — not what a generic fact table "usually" has.
2. **The business context from the dbt exposure** (Step 1 in SKILL.md), or the user's own explanation if no exposure exists.

If you have neither, don't suggest metrics — ask what the table represents first.

## Pattern: per-stage timestamp columns → stage conversion metrics

A common shape on funnel/pipeline fact tables is one timestamp column per stage the record can pass through:

```yaml
columns:
  - name: entered_prospecting_at
  - name: entered_qualification_at
  - name: entered_proposal_at
  - name: entered_closed_won_at
  - name: entered_closed_lost_at
```

This shape supports:

- **Stage duration**: time between consecutive non-null stage timestamps for a given record (`entered_proposal_at - entered_qualification_at`).
- **Stage-to-stage conversion rate**: `count(records where entered_X_at is not null and entered_Y_at is not null) / count(records where entered_X_at is not null)` for adjacent stages.
- **Overall win rate**: `count(entered_closed_won_at is not null) / count(entered_closed_won_at is not null OR entered_closed_lost_at is not null)`.

Only propose the specific stages that actually exist as columns — don't assume a generic sales funnel shape (e.g. don't assume "qualification" exists just because "prospecting" and "proposal" do).

## Other shapes worth recognizing

- **A single `status`/`stage` column with no per-stage timestamps** → can support a distribution/count-by-status measure, but *not* a duration or conversion-rate metric — there's no time dimension to compute a rate from. Don't propose a conversion metric here; propose a count-by-status breakdown instead.
- **An amount/value column alongside a status column** (e.g. `opportunity_amount`, `stage`) → supports weighted-pipeline metrics (`sum(amount) where stage not in (closed_won, closed_lost)`), but only if the exposure/user context confirms this is genuinely how the business values open pipeline — don't assume every amount column should be summed for every status.
- **A boolean/flag column** (`is_converted`, `is_churned`) → supports a straightforward rate measure (`count(where flag) / count(*)`), which is low-risk to propose since it needs no invented logic.
- **Event-level fact tables with a repeated grain per entity** (e.g. one row per page view, one row per activity) → be cautious proposing "conversion" metrics directly on the fact; often the correct move is a *derived* measure at a different grain, which may be better served by a dbt model change rather than a LookML measure. If the correct fix looks like it needs new dbt logic, say so and stop — that's out of scope for this skill.

## How to present suggestions

- List each suggested metric with the plain-language business question it answers, the columns it would use, and the LookML `measure:` you'd write for it.
- Never write the suggested measure into the file until the user confirms which ones they want.
- If a suggested metric requires calculating something dbt hasn't already precomputed (e.g. a time delta between two `dimension_group` timestamps), show the LookML `sql:` you'd use — LookML supports this directly (`sql: ${entered_proposal_raw} - ${entered_qualification_raw} ;;` with an appropriate `type: duration` measure) — but flag if the calculation would be meaningfully more reliable if computed once in dbt instead of on every query.
