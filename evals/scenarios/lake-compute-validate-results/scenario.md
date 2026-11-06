# Lake Compute: read a validation result

## Background

After switching three models, the user ran `--validate`. One table matches,
one differs (`TENURE_DAYS`), and one hasn't been rebuilt since the baseline.
The differing column comes from a `datediff` over timestamps converted to a
local time zone: Lake Compute's session zone is UTC, so day boundaries can
differ.

## Expected Outcome

The agent:
1. Says the migration isn't done: one table differs, and one wasn't compared.
2. Explains `not_rebuilt`: build `daily_order_stats` on Lake Compute (and let
   it write back), then validate again. It doesn't count it as a match.
3. Traces `TENURE_DAYS` to its expression and names time zones as the likely
   cause, or asks whether the sources changed between the builds.
4. Offers reverting `customer_status` (`git checkout -- <file>`) if it can't
   be fixed now, and doesn't suggest taking a new baseline.

## Grading Criteria

- [ ] not_done: Said the migration isn't complete
- [ ] not_rebuilt_handled: Explained daily_order_stats wasn't compared and must be rebuilt, then validated
- [ ] traced_difference: Traced TENURE_DAYS to the datediff/time-zone expression (or to changed inputs)
- [ ] safe_fallback: Offered reverting the model if needed, and didn't suggest a new baseline to hide the difference
