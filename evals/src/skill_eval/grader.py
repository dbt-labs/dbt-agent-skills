"""Grading utilities for skill evaluation."""

import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

GRADING_PROMPT_TEMPLATE = """You are grading an AI assistant's response to a task.

## Task Given
{prompt}

## Expected Behavior & Grading Criteria
{scenario}

## Assistant's Response
{output}

## Tools & Resources Used
{tools_used}

## Modified Files
{modified_files}

---

Grade this response on the following dimensions:

### 1. Task Completion
Did the assistant accomplish the main task described in the prompt?

### 2. Tool Usage
Were the appropriate tools used for this task? Consider:
- Did it use the tools that were available and relevant?
- Did it avoid unnecessary tool calls?
- If MCP servers were available, did it leverage them appropriately?
- If skills were available, did it invoke them when relevant?

### 3. Solution Quality
How good is the solution? Consider correctness, completeness, and clarity.

---

Respond with ONLY a YAML block (no markdown fences), using this exact format:

success: true or false (did it accomplish the main task?)
score: 1-5 (1=failed, 2=poor, 3=acceptable, 4=good, 5=excellent)
tool_usage: appropriate, partial, or inappropriate (did it use the right tools?)
notes: brief explanation of your grade (one line)
"""


def build_grading_prompt(
    scenario_dir: Path,
    output_dir: Path,
) -> str:
    """Build the grading prompt for a scenario/skill-set combination."""
    # Load scenario description and criteria
    scenario_file = scenario_dir / "scenario.md"
    scenario_content = scenario_file.read_text() if scenario_file.exists() else "No scenario description provided."

    # Load the original prompt
    prompt_file = scenario_dir / "prompt.txt"
    prompt_content = prompt_file.read_text() if prompt_file.exists() else "No prompt provided."

    # Load the assistant's output
    output_file = output_dir / "output.md"
    output_content = output_file.read_text() if output_file.exists() else "No output recorded."

    # Load metadata for tools used
    metadata_file = output_dir / "metadata.yaml"
    tools_used = []
    skills_invoked = []
    skills_available = []
    mcp_servers = []

    if metadata_file.exists():
        with metadata_file.open() as f:
            metadata = yaml.safe_load(f)
            tools_used = metadata.get("tools_used", [])
            skills_invoked = metadata.get("skills_invoked", [])
            skills_available = metadata.get("skills_available", [])
            mcp_servers = metadata.get("mcp_servers", [])

    # Build tools section with clear availability vs usage
    tools_lines = ["Tools called:"]
    tools_lines.extend(f"  - {t}" for t in tools_used) if tools_used else tools_lines.append("  (none)")

    if skills_available:
        tools_lines.append("\nSkills available:")
        tools_lines.extend(f"  - {s}" for s in skills_available)
        tools_lines.append("\nSkills actually invoked:")
        tools_lines.extend(f"  - {s}" for s in skills_invoked) if skills_invoked else tools_lines.append("  (none)")

    if mcp_servers:
        tools_lines.append("\nMCP servers configured:")
        for server in mcp_servers:
            if isinstance(server, dict):
                name = server.get("name", "unknown")
                status = server.get("status", "unknown")
                tools_lines.append(f"  - {name} (status: {status})")
            else:
                tools_lines.append(f"  - {server}")

    tools_str = "\n".join(tools_lines)

    # List modified files in context/
    context_dir = output_dir / "context"
    modified_files = []
    if context_dir.exists():
        for f in context_dir.rglob("*"):
            if f.is_file():
                rel_path = f.relative_to(context_dir)
                modified_files.append(str(rel_path))

    modified_files_str = "\n".join(f"- {f}" for f in modified_files) if modified_files else "No files modified."

    return GRADING_PROMPT_TEMPLATE.format(
        prompt=prompt_content,
        scenario=scenario_content,
        output=output_content,
        tools_used=tools_str,
        modified_files=modified_files_str,
    )


def parse_grade_response(response: str) -> dict:
    """Parse the YAML grade response from Claude."""
    # Try to extract YAML from the response (handle markdown fences if present)
    yaml_match = re.search(r"```ya?ml?\s*(.*?)\s*```", response, re.DOTALL)
    if yaml_match:
        yaml_content = yaml_match.group(1)
    else:
        # Assume the whole response is YAML
        yaml_content = response.strip()

    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            return {"success": None, "score": None, "notes": f"Failed to parse: {response[:100]}"}

        return {
            "success": parsed.get("success"),
            "score": parsed.get("score"),
            "tool_usage": parsed.get("tool_usage"),
            "criteria": parsed.get("criteria", {}),
            "notes": parsed.get("notes", ""),
            "observations": parsed.get("observations", ""),
        }
    except yaml.YAMLError as e:
        return {"success": None, "score": None, "notes": f"YAML parse error: {e}"}


def call_claude_grader(prompt: str) -> str:
    """Call Claude CLI to grade a response."""
    cmd = [
        "claude",
        "--print",
        "-p",
        prompt,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "error: timeout"
    except Exception as e:
        return f"error: {e}"


def auto_grade_run(run_dir: Path, scenarios_dir: Path) -> dict:
    """Auto-grade all outputs in a run using Claude."""
    results: dict = {}

    for scenario_output_dir in sorted(run_dir.iterdir()):
        if not scenario_output_dir.is_dir() or scenario_output_dir.name.startswith("."):
            continue

        scenario_name = scenario_output_dir.name
        scenario_dir = scenarios_dir / scenario_name
        results[scenario_name] = {}

        for skill_set_dir in sorted(scenario_output_dir.iterdir()):
            if not skill_set_dir.is_dir():
                continue

            skill_set_name = skill_set_dir.name

            # Build and send grading prompt
            grading_prompt = build_grading_prompt(scenario_dir, skill_set_dir)
            response = call_claude_grader(grading_prompt)
            grade = parse_grade_response(response)

            results[scenario_name][skill_set_name] = grade

    grades = {
        "graded_at": datetime.now().isoformat(),
        "grader": "claude-auto",
        "results": results,
    }

    return grades


def init_grades_file(run_dir: Path) -> Path:
    """Create initial grades.yaml file for a run."""
    grades_file = run_dir / "grades.yaml"

    if grades_file.exists():
        return grades_file

    results: dict = {}
    for scenario_dir in run_dir.iterdir():
        if not scenario_dir.is_dir():
            continue
        scenario_name = scenario_dir.name
        results[scenario_name] = {}

        for skill_set_dir in scenario_dir.iterdir():
            if not skill_set_dir.is_dir():
                continue
            skill_set_name = skill_set_dir.name
            results[scenario_name][skill_set_name] = {
                "success": None,
                "score": None,
                "criteria": {},
                "notes": "",
                "observations": "",
            }

    grades = {
        "graded_at": None,
        "grader": "human",
        "results": results,
    }

    with grades_file.open("w") as f:
        yaml.dump(grades, f, default_flow_style=False, sort_keys=False)

    return grades_file


def load_grades(run_dir: Path) -> dict:
    """Load grades from a run directory."""
    grades_file = run_dir / "grades.yaml"
    if not grades_file.exists():
        return {}
    with grades_file.open() as f:
        return yaml.safe_load(f)


def save_grades(run_dir: Path, grades: dict) -> None:
    """Save grades to a run directory."""
    grades["graded_at"] = datetime.now().isoformat()
    grades_file = run_dir / "grades.yaml"
    with grades_file.open("w") as f:
        yaml.dump(grades, f, default_flow_style=False, sort_keys=False)
