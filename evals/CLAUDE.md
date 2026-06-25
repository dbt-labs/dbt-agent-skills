# Skill Eval CLI

See [AGENTS.md](AGENTS.md) for development conventions.

Quick reference:

- Use `typer.echo()` for CLI output, `logger` from `logging.py` for progress
- Run `uv run ty check src/` before committing
- Add tests for new features
- Check dataclasses in `models.py` and `runner.py` when modifying commands
