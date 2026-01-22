"""Data models for skill evaluation."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillSet:
    """A combination of skills and MCP servers to test."""

    name: str
    skills: list[str] = field(default_factory=list)
    mcp_servers: dict = field(default_factory=dict)  # MCP server config (mcpServers format)
    allowed_tools: list[str] = field(default_factory=list)  # If empty, allows all tools


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

    skill_sets = [
        SkillSet(
            name=s["name"],
            skills=s.get("skills", []),
            mcp_servers=s.get("mcp_servers", {}),
            allowed_tools=s.get("allowed_tools", []),
        )
        for s in data.get("sets", [])
    ]

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
