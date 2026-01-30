# Scripts

Utility scripts for managing dbt agent skills.

## dbt-skills-install (Experimental)

Install agent skills from `dbt_packages` to Claude Code. This script is for **skills bundled with dbt packages** (e.g., skills shipped by package authors alongside their dbt packages), not for skills from this repository.

It scans your dbt project's packages for `SKILL.md` files and installs them using the [Vercel Skills CLI](https://github.com/vercel-labs/skills).

### Usage

```bash
# Run from your dbt project directory
./dbt-skills-install                    # Interactive install from ./dbt_packages
./dbt-skills-install --all              # Install all skills (no prompts)
./dbt-skills-install --list             # List available skills without installing
./dbt-skills-install --global           # Install globally (~/.claude/skills/)
./dbt-skills-install --dir ./packages   # Use custom directory
./dbt-skills-install --help             # Show help
```

### Requirements

- bash
- node/npx (for the Vercel Skills CLI)

### Optional

- [gum](https://github.com/charmbracelet/gum) for prettier prompts

```bash
brew install gum          # macOS
sudo apt install gum      # Debian/Ubuntu
```

### How it works

1. Scans `./dbt_packages` (or specified directory) for skills
2. Looks for `SKILL.md` files in package roots, `skills/`, and `.claude/skills/` directories
3. Presents an interactive menu to select which skills to install
4. Installs selected skills using `npx skills add`

---

## generate_marketplace.py

Generates the `marketplace.json` file for the Claude Code plugin system from `SKILL.md` files in this repository.

### Usage

```bash
# From the repository root
python3 scripts/generate_marketplace.py
```

### Output

Creates `.claude-plugin/marketplace.json` with metadata for all skills in the repository.

### When to run

Run this script after adding or modifying skills to update the marketplace manifest.
