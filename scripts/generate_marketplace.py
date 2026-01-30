#!/usr/bin/env python3
"""Generate marketplace.json from SKILL.md files in the repository."""

import json
import re
from pathlib import Path

# Category mapping based on skill name patterns
CATEGORY_MAP = {
    "fetching-dbt-docs": "documentation",
    "configuring-dbt-mcp-server": "integration",
    "troubleshooting-dbt-job-errors": "operations",
    "building-dbt-semantic-layer": "semantic-layer",
    "answering-natural-language-questions-with-dbt": "semantic-layer",
    "migrating-dbt-core-to-fusion": "migration",
    "adding-dbt-unit-test": "testing",
}

DEFAULT_CATEGORY = "analytics"

MARKETPLACE_METADATA = {
    "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
    "name": "dbt-agent-skills",
    "description": "Skills for working with dbt Core and the dbt Fusion engine - analytics engineering, data modeling, semantic layer, and dbt platform (fka dbt Cloud) operations",
    "owner": {
        "name": "dbt Labs",
        "email": "support@getdbt.com"
    }
}

AUTHOR = {"name": "dbt Labs"}


def parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from SKILL.md content."""
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None

    frontmatter = {}
    for line in match.group(1).strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            frontmatter[key] = value

    return frontmatter


def get_category(skill_name: str) -> str:
    """Determine category based on the skill name."""
    return CATEGORY_MAP.get(skill_name, DEFAULT_CATEGORY)


def get_source_path(skill_path: Path, repo_root: Path) -> str:
    """Get the relative source path for the skill."""
    skill_dir = skill_path.parent
    relative_path = skill_dir.relative_to(repo_root)
    return f"./{relative_path}"


def find_skill_files(repo_root: Path) -> list[Path]:
    """Find all SKILL.md files in the repository."""
    skill_files = list(repo_root.glob("**/SKILL.md"))
    # Exclude any in hidden directories or common non-skill locations
    skill_files = [
        f for f in skill_files
        if not any(part.startswith('.') for part in f.parts)
    ]
    return sorted(skill_files)


def generate_marketplace(repo_root: Path) -> dict:
    """Generate the complete marketplace.json structure."""
    skill_files = find_skill_files(repo_root)
    plugins = []

    for skill_path in skill_files:
        content = skill_path.read_text()
        frontmatter = parse_frontmatter(content)

        if not frontmatter:
            print(f"Warning: Could not parse frontmatter from {skill_path}")
            continue

        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name or not description:
            print(f"Warning: Missing name or description in {skill_path}")
            continue

        plugin = {
            "name": name,
            "description": description,
            "author": AUTHOR,
            "source": get_source_path(skill_path, repo_root),
            "category": get_category(name)
        }
        plugins.append(plugin)

    marketplace = {**MARKETPLACE_METADATA, "plugins": plugins}
    return marketplace


def main():
    # Find repo root (where .claude-plugin directory should be)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Generate marketplace
    marketplace = generate_marketplace(repo_root)

    # Ensure .claude-plugin directory exists
    output_dir = repo_root / ".claude-plugin"
    output_dir.mkdir(exist_ok=True)

    # Write marketplace.json
    output_path = output_dir / "marketplace.json"
    with open(output_path, 'w') as f:
        json.dump(marketplace, f, indent=2)
        f.write('\n')

    print(f"Generated {output_path} with {len(marketplace['plugins'])} plugins")


if __name__ == "__main__":
    main()
