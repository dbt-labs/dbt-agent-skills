# Skill Evaluation Tool - Developer Guide

This document covers conventions and patterns for working on the `skill-eval` CLI tool.

## Architecture Overview

```
src/skill_eval/
├── cli.py       # Typer CLI commands (run, grade, report, review)
├── models.py    # Data models: Scenario, SkillSet, load_scenario()
├── runner.py    # Execution: Runner class, RunResult, RunTask
├── grader.py    # Auto-grading with Claude CLI
└── reporter.py  # Report generation from grades
```

**Data flow:** `cli.py` loads scenarios via `models.py`, executes via `runner.py`, grades via `grader.py`, and reports via `reporter.py`.

## CLI Framework: Typer

We use [Typer](https://typer.tiangolo.com/) for the CLI.

### Output with typer.echo()

Always use `typer.echo()` for user-facing output, never `print()`:

```python
# Good
typer.echo(f"Running scenario: {name}")
typer.echo("Error: file not found", err=True)

# Bad
print(f"Running scenario: {name}")
```

### Adding Commands

New commands go in `cli.py`:

```python
@app.command()
def mycommand(
    arg: str = typer.Argument(..., help="Required argument"),
    flag: bool = typer.Option(False, "--flag", "-f", help="Optional flag"),
) -> None:
    """Command description shown in --help."""
    typer.echo(f"Running with {arg}")
```

## Data Models

### Dataclasses (models.py, runner.py)

When modifying CLI commands that work with scenarios or skill sets, check if the underlying dataclasses need updates:

**In `models.py`:**
- `Grade` - grading result (success, score, tool_usage, notes, etc.)
- `SkillSet` - skills, mcp_servers, allowed_tools
- `Scenario` - name, path, prompt, skill_sets, description

**In `runner.py`:**
- `RunResult` - scenario results with output, success, tools_used, skills_invoked, etc.
- `RunTask` - task definition for parallel execution (scenario, skill_set, run_dir)

Use `dataclasses.asdict()` to convert dataclasses to dicts for YAML serialization.

When modifying grading:
1. Update `Grade` dataclass in `models.py` if adding new fields
2. Update `GRADING_PROMPT_TEMPLATE` in `grader.py` if changing what Claude evaluates
3. Update `parse_grade_response()` to extract new fields into Grade
4. Update `reporter.py` to display new fields

## Modifying Features - Checklist

### Adding a new CLI subcommand

1. Add command function in `cli.py` with `@app.command()`
2. Use `typer.echo()` for all output
3. Add tests in `tests/`
4. Update `README.md` usage section
5. Run `uv run ty check src/`

### Adding a new field to skill-sets.yaml

1. Update `SkillSet` dataclass in `models.py`
2. Update `load_scenario()` to parse the new field
3. Update `Runner.run_scenario()` if it affects execution
4. Add tests for the new field

### Adding new run output/metadata fields

1. Update `RunResult` dataclass in `runner.py`
2. Update `_parse_json_output()` to extract new data from Claude's output
3. Update metadata.yaml writing in `run_scenario()`
4. Update grader if it should evaluate the new field
5. Update reporter if it should display the new field
6. Add tests

### Modifying grading criteria

1. Update `GRADING_PROMPT_TEMPLATE` in `grader.py`
2. Update `parse_grade_response()` to handle new fields
3. Update `init_grades_file()` for manual grading template
4. Update `reporter.py` to show new fields in reports
5. Add tests

## Parallel Execution

We use `concurrent.futures.ThreadPoolExecutor` for parallel runs:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_task = {executor.submit(fn, task): task for task in tasks}
    for future in as_completed(future_to_task):
        result = future.result()
```

See `Runner.run_parallel()` in `runner.py` for the full implementation.

## Type Checking with ty

Run the [ty](https://github.com/astral-sh/ty) type checker before committing:

```bash
uv run ty check src/
```

Fix any type errors. Common issues:
- Mixed dict types need explicit annotations
- Optional fields need `| None` types
- Use `list[str]` not `List[str]` (Python 3.11+)

## Testing

Tests live in `tests/` and use pytest.

### Running Tests

```bash
uv run pytest                    # all tests
uv run pytest tests/test_cli.py  # specific file
uv run pytest -k "test_grade"    # by name pattern
```

### Test Requirements

**Every new feature needs tests.** This includes:
- New CLI commands
- New options/flags on existing commands
- Changes to data models
- New grading/reporting logic

## Dependencies

Key dependencies in `pyproject.toml`:
- `typer` - CLI framework
- `pyyaml` - YAML parsing
- `claude-code-transcripts` - HTML transcript generation

Dev dependencies:
- `pytest` - testing
- `ty` - type checking
