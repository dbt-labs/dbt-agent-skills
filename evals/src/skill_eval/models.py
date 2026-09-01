"""Data models for skill evaluation."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Grade:
    """Result of grading a scenario run."""

    success: bool | None = None
    score: int | None = None
    tool_usage: str | None = None  # "appropriate", "partial", or "inappropriate"
    criteria: dict = field(default_factory=dict)
    notes: str = ""
    observations: str = ""
    # Skill usage tracking (computed from run metadata)
    skills_available: list[str] = field(default_factory=list)
    skills_invoked: list[str] = field(default_factory=list)
    skill_usage_pct: float | None = None


@dataclass
class SkillSet:
    """A combination of skills and MCP servers to test."""

    name: str
    model: str
    skills: list[str] = field(default_factory=list)
    mcp_servers: dict = field(default_factory=dict)  # MCP server config (mcpServers format)
    allowed_tools: list[str] = field(default_factory=list)  # If empty, allows all tools
    extra_prompt: str = ""  # Additional text appended to the base prompt
    setup: list[str] = field(default_factory=list)  # Commands to run before Claude
    # If True (default), only MCP servers from this set's mcp_servers are used —
    # Claude Desktop / user / project MCP config is ignored. Set to False to opt out.
    strict_mcp_config: bool = True


@dataclass
class Scenario:
    """A test scenario with prompt and skill sets."""

    name: str
    path: Path
    prompt: str
    skill_sets: list[SkillSet]
    description: str = ""

    @property
    def context_dir(self) -> Path:
        """Path to context files for this scenario."""
        return self.path / "context"


def load_scenario(scenario_dir: Path) -> Scenario:
    """Load a scenario from a directory."""
    name = scenario_dir.name
    prompt = (scenario_dir / "prompt.txt").read_text().strip()

    skill_sets_file = scenario_dir / "skill-sets.yaml"
    with skill_sets_file.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"skill-sets.yaml in '{name}' is empty or not a mapping with a 'sets' list."
        )

    skill_sets = []
    for s in data.get("sets", []):
        if not s.get("model"):
            raise ValueError(
                f"skill-sets.yaml in '{name}' is missing a required 'model' field "
                f"for set '{s.get('name', '?')}'. Every set must declare a model "
                "(e.g. `model: sonnet`) so runs are reproducible."
            )
        skill_sets.append(
            SkillSet(
                name=s["name"],
                model=s["model"],
                skills=s.get("skills", []),
                mcp_servers=s.get("mcp_servers", {}),
                allowed_tools=s.get("allowed_tools", []),
                extra_prompt=s.get("extra_prompt", ""),
                setup=s.get("setup", []),
                strict_mcp_config=s.get("strict_mcp_config", True),
            )
        )

    description = ""
    scenario_md = scenario_dir / "scenario.md"
    if scenario_md.exists():
        description = scenario_md.read_text()

    return Scenario(
        name=name,
        path=scenario_dir,
        prompt=prompt,
        skill_sets=skill_sets,
        description=description,
    )
