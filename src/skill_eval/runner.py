"""Runner for executing scenarios against skill variants."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from skill_eval.models import Scenario, SkillSet


@dataclass
class RunResult:
    """Result of running a scenario with a skill set."""

    scenario_name: str
    skill_set_name: str
    output: str
    success: bool
    error: str | None = None


class Runner:
    """Executes scenarios against skill variants."""

    def __init__(self, evals_dir: Path) -> None:
        self.evals_dir = evals_dir
        self.variants_dir = evals_dir / "variants"
        self.runs_dir = evals_dir / "runs"

    def create_run_dir(self) -> Path:
        """Create a timestamped directory for this run."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        run_dir = self.runs_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def prepare_environment(
        self,
        context_dir: Path | None,
        skills: list[str],
    ) -> Path:
        """Create isolated environment with only specified skills."""
        env_dir = Path(tempfile.mkdtemp(prefix="skill-eval-"))

        if context_dir and context_dir.exists():
            shutil.copytree(context_dir, env_dir, dirs_exist_ok=True)

        if skills:
            skills_dir = env_dir / ".claude" / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            for skill_path in skills:
                src = self.variants_dir / skill_path
                if src.exists():
                    dest = skills_dir / skill_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, dest)

        return env_dir

    def run_claude(
        self,
        env_dir: Path,
        prompt: str,
    ) -> tuple[str, bool, str | None]:
        """Run Claude Code with isolated config and capture output."""
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(env_dir / ".claude")
        env["HOME"] = str(env_dir)

        try:
            result = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--dangerously-skip-permissions",
                    "-p",
                    prompt,
                ],
                cwd=env_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
            output = result.stdout + result.stderr
            return output, result.returncode == 0, None
        except subprocess.TimeoutExpired:
            return "", False, "Timeout after 5 minutes"
        except Exception as e:
            return "", False, str(e)

    def run_scenario(
        self,
        scenario: Scenario,
        skill_set: SkillSet,
        run_dir: Path,
    ) -> RunResult:
        """Run a single scenario with a skill set."""
        env_dir = self.prepare_environment(
            context_dir=scenario.context_dir,
            skills=skill_set.skills,
        )

        output, success, error = self.run_claude(env_dir, scenario.prompt)

        output_dir = run_dir / scenario.name / skill_set.name
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "output.md").write_text(output)

        shutil.rmtree(env_dir, ignore_errors=True)

        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output=output,
            success=success,
            error=error,
        )
