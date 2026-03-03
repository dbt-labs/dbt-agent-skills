# Migration Triage References

## WHAT
This directory contains reference material for the Fusion migration triage skill's 4-category classification framework.

## LAYOUT

- [error-patterns-reference.md](error-patterns-reference.md) — Complete catalog of error patterns organized by type (YAML, packages, config/API, SQL/Jinja, static analysis, framework)
- [classification-categories.md](classification-categories.md) — Detailed definitions for each triage category (A: auto-fixable, B: guided fixes, C: needs input, D: blocked)

## CONTRIBUTING

If you encounter a new migration error pattern not covered here, add it to the appropriate section of `error-patterns-reference.md` and update `classification-categories.md` if it represents a new sub-pattern.
