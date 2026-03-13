## Success Metrics and Definition of Done

Use these measures to validate SAO code/config quality and savings impact.

### Primary Metrics (From Code-Driven Changes)

- Runtime trend reduction for SAO-enabled paths
- Cost trend reduction for SAO-enabled paths
- Increase in expected skip rate for unchanged nodes
- Freshness SLA compliance for critical models and sources

### Supporting Metrics

- Number of models saved from unnecessary rebuilds
- Number of reruns avoided
- Reduction in config override sprawl over time
- Percentage of models inheriting project defaults

### Developer Efficiency Signals

- Faster feedback loops in development
- Faster review/debug cycles enabled by Fusion capabilities
- Time saved per delivery unit (new pipeline or enhancement)

### Definition of Done

- Project-level SAO defaults are established and documented
- Model-level overrides are minimal, justified, and reviewed
- Baseline-vs-post metrics show measurable improvement (for example, 10%+ cost or runtime reduction where feasible)
- Code rollback strategy exists for config regressions
- Out-of-scope platform dependencies are tracked and handed off

See [Platform and Job Adjustments (Out of Scope)](platform-and-job-adjustments.md).
