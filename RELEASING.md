# Releasing

This document covers how updates to this repository are published to plugin marketplaces.

## Before Releasing

Bump the `version` field in each plugin manifest that has changed:

| Plugin | Manifest files |
|--------|----------------|
| dbt | `skills/dbt/.claude-plugin/plugin.json`, `skills/dbt/.cursor-plugin/plugin.json` |
| dbt-migration | `skills/dbt-migration/.claude-plugin/plugin.json` |
| dbt-extras | `skills/dbt-extras/.claude-plugin/plugin.json` |
| tessl (all plugins) | `tile.json` |

---

## Cursor Plugin Marketplace

The dbt Agent Skills plugins are listed in the [Cursor plugin marketplace](https://www.cursor.com/plugins).

After merging updates to `main`, notify the Cursor marketplace team so changes can be synced to the plugin listing:

- Email: marketplace-publishing@cursor.com

## skills.sh

[skills.sh](https://skills.sh) automatically scans this repository — no manual action needed after merging to `main`.

## Claude Marketplace

The Claude marketplace automatically scans this repository — no manual action needed after merging to `main`.

## Tessl

[Tessl](https://tessl.io) has a GitHub Action configured in this repo that handles submission automatically on merge to `main`. Skills are evaluated against Tessl's quality standards and added to their open registry.

