How dbt Labs reduced dbt-related compute costs by 64% with Fusion and state-aware orchestration
Brandon Thomson,
Pat Kearns,
Ken Ostner
last updated on Feb 13, 2026

When you're running analytics for a company that builds analytics infrastructure, expectations are high. Our internal analytics project processes roughly 1,500 models across multiple jobs on various schedules, serving everything from executive dashboards to operational metrics. As our data estate grew, so did our compute costs—and we needed a solution that would let us meet our data freshness requirements without breaking the budget.

The answer came from our own product roadmap: migrating to dbt’s next-generation Fusion engine and implementing State-Aware Orchestration (SAO). What we didn't anticipate was just how transformative this journey would be. Through a combination of platform migration, intelligent orchestration, and thoughtful optimization, we achieved a 64% reduction in compute costs while actually simplifying our job architecture.

This is the story of how we got there—including the false starts, lessons learned, and recommendations for teams considering a similar path.

The challenge: Balancing freshness and cost
Before our migration, we were running on legacy dbt infrastructure with complex job configurations that had accumulated over years. We had multiple projects, intricate package dependencies creating technical debt, and an ever-growing compute bill.

The fundamental tension was clear: our stakeholders needed fresh data to make decisions, but every model run cost money. We were rebuilding models whether they needed it or not, reprocessing unchanged views, and running transformations even when the source data hadn't been updated. We needed intelligence in our orchestration—a way for dbt to understand what actually needed to run.

At a high level, State-Aware Orchestration changes the fundamental question dbt asks:

Traditional orchestration asks: “Is it time to run?”

SAO asks: “What actually changed?”

If nothing upstream has changed—or if a model already satisfies its freshness requirement—dbt simply reuses the existing result. No rebuild. No wasted compute.

That shift sounds subtle, but at scale, it’s transformative.

Phase 1: The migration to Fusion (May–August 2025)
We kicked off our Fusion migration on May 21st, 2025. The timeline was aggressive but achievable: we completed two smaller projects by May 28th and had our entire data estate running on Fusion by July 10th. This phase wasn’t about savings yet. It was about unlocking the foundation that makes intelligent orchestration possible.

The upgrade process wasn't without challenges that you’d expect when migrating to an Alpha version. This is why we at dbt Labs make it a practice to use our software first before even rolling it out to customers in a Beta stage. We encountered parse and compile issues that required "whack-a-mole" fixes, dealt with package updates cascading through dependencies, and coordinated with package maintainers to ensure compatibility. The key technical changes included moving custom configs under config.meta, adding arguments to tests due to spec changes, and relocating several config properties from top-level to config blocks.

Fortunately, dbt's Autofix tool handled most of these transformations effectively. For our largest project (Internal Analytics), we created a manual fix branch that fed improvements back into the Autofix script, then used the automated tool for the final migration.

One critical decision: we maintained the ability to revert between Fusion and hosted dbt using the same configuration. This flexibility proved essential during July when we hit production stability issues. As a Fusion Canary project—essentially an advanced staging environment—we experienced bouts of instability as new versions rolled out. When issues arose, we'd roll back to the prior stable version or switch back to Mantle while the Fusion team marked the problematic version as bad and fixed it in the next release.

By August, we had stabilized on Fusion and completed the migration phase.

Phase 2: Activation and immediate wins (August–October 2025)
With Fusion stable, we turned our attention to State-Aware Orchestration. We treated this as a control experiment: same jobs, same schedules, same models—just with state awareness turned on.

The results were immediate: 9% cost savings against our data warehouse with zero configuration effort.

SAO delivered these savings by making intelligent decisions about what actually needed to run. It stopped rebuilding unchanged views, skipped models when sources had no new data, and reused approximately 35% of models daily. We switched our jobs to state-aware run methods, conducted smoke tests to verify behavior, and watched the compute costs drop.

This was our "activation" phase—proof that the technology worked and delivered value out of the box. But we knew there was more optimization potential if we were willing to tune our approach.

Phase 3: The optimization journey (October 2025–January 2026)
Emboldened by our initial wins, we set out to optimize further. Our first approach seemed logical: map source data frequency to dashboard SLAs, building a detailed matrix of requirements and implementing directory-level configs in dbt_project.yml.

This "right-to-left" approach failed spectacularly. We discovered we lacked documented SLAs, had unclear source freshness thresholds, and created significant mental overhead managing mixed configuration levels. Worse, our configuration was still tied to our old, complex job architecture.

We pivoted to simplification. Instead of engineering an elaborate system, we aligned on business needs: The majority (90%) of our models just needed to be fresh on a daily (24-hour) basis. The remaining models had varying freshness requirements, from 1 hour to 7 days. We found that we could cover all of these refresh intervals across only 2 jobs, compared to the 10 jobs we had before.

Our configuration became elegantly simple. The project-wide default specified 24-hour freshness:

# dbt_project.yml
...

models:
	+freshness:
    build_after:
      count: "{{ var('build_after_count', 1) }}"
      period: "{{ var('build_after_period', 'day') }}"
      updates_on: any
This single default replaced dozens of schedule-based assumptions we had previously encoded in job logic. But why variables? Originally, we thought we could get away with only one job - an hourly job. When we had the default project config set to one day, we found that the time of day at which that model runs could drift throughout the week. We quickly realized that we had lost our ability to guarantee the last complete day of data when our business users logged on in the morning. As a result, we decided on three jobs: a weekly job (for capturing long-range late-arriving events), a daily job, and an hourly job.

The intention was that our daily job always runs after midnight UTC, and that it would build all of our models, with any level of freshness, only if there was new data. These variables allow us to overwrite the project-default freshness to ensure this is possible. Here's what our job config looks like for our daily job:

dbt build --vars '{build_after_count: 0, build_after_period: minute}'
In the above command, we are telling dbt to “build all models that have ANY new data since they last ran.” For some of our sources, we just don’t see new data every day! Not many people register for Coalesce in January before registration has opened up, for example. Compared to running this daily job without SAO, we are still managing to build 20% fewer models, and we can guarantee last complete day data.

For operational models requiring hourly updates, we added model-specific overrides directly in the model configuration. This ensures that throughout the day, models will update on the agreed upon cadence (intra day updates).

# example_model.yml
...

- name: example_model
  description: A model that updates hourly.
  config:
	  freshness:
		  build_after:
			  count: 1
			  period: hour
			  updates_on: any
We hit a snag with updates_on: all—applying it too broadly caused our hourly job to exceed one-hour runtime, creating job queuing and missed runs. We rolled back to more selective use, reserving this setting for specific incremental models where all upstream dependencies updated on a regular cadence.

The results: 64% cost reduction and simplified operations
The numbers speak for themselves. Our initial Fusion enablement delivered 9% savings. Tuned SAO configurations added another 55%. Total reduction: 64% in compute costs.

But the benefits extended beyond the bottom line. We simplified our job architecture dramatically—consolidating many disparate jobs into three main workflows (hourly, daily, weekly). Our mental model became cleaner. Our configurations aligned with actual business needs rather than technical constraints.

A significant portion of our models now get reused across runs, eliminating unnecessary rebuilds. Our data remains fresh for stakeholders, but we're only paying for the transformations that truly need to happen. The biggest gains didn’t come from more rules—they came from fewer jobs and clearer intent.

Watch the on-demand webinar: Smarter pipelines, 29%+ warehouse savings: How the dbt Fusion engine drives more cost-effective data ops
What's left to do
Some challenges remain, particularly around seeding data for new models. Since SAO might not detect a need to use new data initially (if sources haven't hit their SLA yet), we occasionally encounter logic issues on first runs that resolve themselves subsequently. We need a better workflow for new model builds after PR merges.

We're also working to make our jobs more targeted, minimizing SAO's overhead by explicitly excluding sources we know should be skipped rather than having SAO monitor everything. Even intelligent orchestration has computational costs, albeit much reduced compared to running an unchanged model.

Lessons learned: What we'd tell other teams
If you're considering a similar journey, here's what we learned:

Start simple. Our "activation" phase delivered 9% savings with no tuning. Don't over-engineer your initial SAO configurations—get the quick wins first, then iterate.
Let business needs drive technical decisions. Our elaborate right-to-left mapping failed because we led with technical constraints instead of business requirements. Two freshness tiers (daily and hourly) work better than elaborate matrices.
Be cautious with updates_on: all. This setting has power but requires thoughtful application. Monitor job runtimes to prevent queuing and missed runs. It can have unintended (or intended!) effects when using views or when multiple tables are referenced, but update at vastly different frequencies.
Maintain rollback capability during early phases. The ability to revert between Fusion and Mantle saved us during production instability.
Migration is manageable. Autofix handles most technical changes. The path isn't always linear, but it's navigable.
Simplicity beats complexity. Your job architecture can actually get simpler, not more complex. We went from many jobs to three main workflows and have better outcomes.
The journey from 1,500 models on legacy infrastructure to a 64% cost reduction wasn't just about adopting new technology—it was about rethinking how we orchestrate data transformations. Fusion and State-Aware Orchestration gave us the tools, but the real wins came from aligning our technical implementation with business needs and having the courage to simplify. Intelligent orchestration doesn’t just save money and drive efficiency, it also provides clarity.

For teams running large dbt projects, the promise is real. The path requires iteration, but the destination is worth