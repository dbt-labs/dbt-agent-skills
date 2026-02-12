# Cross-Platform Migration References

## Overview

This directory contains reference documents for migrating a dbt project between data platforms. The migration workflow relies on dbt Fusion's real-time compilation as the primary engine for identifying SQL dialect differences — these references cover the surrounding workflow steps.

## References

| File | Purpose |
|------|---------|
| [installing-dbt-fusion.md](installing-dbt-fusion.md) | How to install and verify dbt Fusion |
| [generating-unit-tests.md](generating-unit-tests.md) | How to generate unit tests on the source platform before migration |
| [switching-profiles.md](switching-profiles.md) | How to configure the target platform profile and update sources |

## Why Only 3 References?

The actual SQL dialect translation is handled entirely by Fusion's compilation and error diagnostics. There's no need to document platform-specific SQL patterns — Fusion identifies them all. These references focus on the workflow steps that surround the Fusion-driven compilation loop:

1. **Installing Fusion** — Prerequisite setup
2. **Generating unit tests** — Pre-migration data capture for validation
3. **Switching profiles** — Configuration changes to point at the target platform
