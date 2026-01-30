"""Runner for executing scenarios against skill variants."""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlparse

import yaml
from claude_code_transcripts import generate_html

from skill_eval.models import Scenario, SkillSet


@dataclass
class RunResult:
    """Result of running a scenario with a skill set."""

    scenario_name: str
    skill_set_name: str
    output: str
    success: bool
    error: str | None = None
    skills_invoked: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


@dataclass
class RunTask:
    """A single scenario + skill-set combination to run."""

    scenario: Scenario
    skill_set: SkillSet
    run_dir: Path


class Runner:
    """Executes scenarios against skill variants."""

    def __init__(self, evals_dir: Path) -> None:
        self.evals_dir = evals_dir
        self.repo_dir = evals_dir.parent  # Skills are relative to repo root
        self.runs_dir = evals_dir / "runs"

    def _get_claude_credentials(self) -> str | None:
        """Read Claude OAuth credentials from macOS Keychain."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_url(self, path: str) -> bool:
        """Check if a skill path is an HTTP(S) URL."""
        try:
            parsed = urlparse(path)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    def _normalize_github_url(self, url: str) -> str:
        """Convert GitHub blob URLs to raw URLs.

        Converts: https://github.com/org/repo/blob/main/path/SKILL.md
        To:       https://raw.githubusercontent.com/org/repo/main/path/SKILL.md
        """
        parsed = urlparse(url)
        if parsed.netloc != "github.com":
            return url

        # GitHub blob URL format: /org/repo/blob/branch/path/to/file
        path_parts = parsed.path.split("/")
        if len(path_parts) >= 5 and path_parts[3] == "blob":
            # Remove "blob" from path: /org/repo/branch/path/to/file
            new_path = "/".join(path_parts[:3] + path_parts[4:])
            return f"https://raw.githubusercontent.com{new_path}"

        return url

    def _download_skill(self, url: str, skills_dir: Path) -> None:
        """Download a skill from an HTTP URL pointing to a SKILL.md file.

        Supports:
        - Raw file URLs (e.g., https://raw.githubusercontent.com/org/repo/main/skill/SKILL.md)
        - GitHub blob URLs (automatically converted to raw URLs)
        - Works with branches, tags, and commit SHAs

        Folder naming (for file organization, not the skill name which comes from frontmatter):
        - Normal case: uses parent folder of SKILL.md from URL path
        - GitHub repo root (SKILL.md at root): uses repository name
        - Other root-level URLs: uses hostname (dots replaced with dashes)
        """
        # Convert GitHub blob URLs to raw URLs
        download_url = self._normalize_github_url(url)

        parsed = urlparse(download_url)
        path = parsed.path.rstrip("/")

        # Extract folder name from URL path
        # For GitHub raw URLs: raw.githubusercontent.com/org/repo/ref/path/to/skill/SKILL.md
        # For other URLs: example.com/path/to/skill/SKILL.md
        all_parts = [p for p in path.split("/") if p]

        if parsed.netloc == "raw.githubusercontent.com":
            # GitHub raw URL format: org/repo/ref/[path/to/skill/]SKILL.md
            # If only 4 parts (org, repo, ref, SKILL.md), skill is at repo root
            if len(all_parts) <= 4:
                folder_name = all_parts[1] if len(all_parts) >= 2 else "downloaded-skill"
            else:
                folder_name = all_parts[-2]  # Parent folder of SKILL.md
        elif len(all_parts) >= 2:
            folder_name = all_parts[-2]  # Parent folder of SKILL.md
        else:
            # Root-level skill on non-GitHub host
            folder_name = parsed.netloc.replace(".", "-")

        dest = skills_dir / folder_name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            with urllib.request.urlopen(download_url, timeout=30) as response:
                content = response.read().decode("utf-8")
                dest.write_text(content)
        except URLError as e:
            raise RuntimeError(f"Failed to download skill from {download_url}: {e}") from e

    def _copy_local_skill(self, skill_path: str, skills_dir: Path) -> None:
        """Copy a local skill (file or folder) to the skills directory."""
        src = self.repo_dir / skill_path
        if not src.exists():
            return

        if src.is_dir():
            # Folder path: copy entire folder
            shutil.copytree(src, skills_dir / src.name)
        else:
            # File path: copy just the file, skill name is parent folder name
            dest = skills_dir / src.parent.name / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)

    def _generate_transcript(
        self, env_dir: Path, output_dir: Path, scenario_name: str, skill_set_name: str
    ) -> None:
        """Generate HTML transcript from Claude's native session file."""
        claude_projects = env_dir / ".claude" / "projects"
        if not claude_projects.exists():
            return

        session_file = next(
            (f for f in claude_projects.glob("*/*.jsonl") if not f.name.startswith("agent-")),
            None,
        )
        if not session_file:
            return

        try:
            transcript_dir = output_dir / "transcript"
            generate_html(session_file, transcript_dir)

            # Update HTML titles to include scenario and skill set info
            custom_title = f"{scenario_name} / {skill_set_name}"
            for html_file in transcript_dir.glob("*.html"):
                content = html_file.read_text()
                # Replace in <title> tags
                content = content.replace(
                    "<title>Claude Code transcript",
                    f"<title>{custom_title}",
                )
                # Replace in <h1> tags - handles both index.html (direct h1)
                # and page-xxx.html (h1 with anchor wrapper)
                content = content.replace(
                    ">Claude Code transcript<",
                    f">{custom_title}<",
                )
                html_file.write_text(content)
        except Exception as e:
            print(f"Warning: transcript generation failed: {e}")

    def create_run_dir(self) -> Path:
        """Create a timestamped directory for this run."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        run_dir = self.runs_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def prepare_environment(
        self,
        scenario_dir: Path,
        context_dir: Path | None,
        skills: list[str],
        mcp_servers: dict | None = None,
    ) -> tuple[Path, Path | None]:
        """Create isolated environment with only specified skills.

        Returns: (env_dir, mcp_config_path)
        """
        env_dir = Path(tempfile.mkdtemp(prefix="skill-eval-"))

        if context_dir and context_dir.exists():
            shutil.copytree(context_dir, env_dir, dirs_exist_ok=True)

        # Create .claude directory
        claude_dir = env_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Copy credentials from keychain to isolated environment
        credentials = self._get_claude_credentials()
        if credentials:
            (claude_dir / ".credentials.json").write_text(credentials)

        # Load skills from local paths or HTTP URLs
        if skills:
            skills_dir = claude_dir / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            for skill_path in skills:
                if self._is_url(skill_path):
                    self._download_skill(skill_path, skills_dir)
                else:
                    self._copy_local_skill(skill_path, skills_dir)

        # Write MCP server config if provided
        mcp_config_path = None
        if mcp_servers:
            mcp_config_path = claude_dir / "mcp-servers.json"
            mcp_config_path.write_text(json.dumps({"mcpServers": mcp_servers}, indent=2))

            # Copy .env from scenario dir if it exists (for MCP servers using --env-file .env)
            env_file = scenario_dir / ".env"
            if env_file.exists():
                shutil.copy(env_file, env_dir / ".env")

        return env_dir, mcp_config_path

    def _parse_json_output(self, json_str: str) -> dict:
        """Parse NDJSON (newline-delimited JSON) output from Claude stream-json format.

        Returns dict with: output_text, skills_invoked, tools_used, and run metadata.
        """
        result = {
            "output_text": "",
            "skills_invoked": [],
            "tools_used": [],
            # From init message
            "model": None,
            "skills_available": [],
            "mcp_servers": [],
            # From result message
            "duration_ms": None,
            "num_turns": None,
            "total_cost_usd": None,
            "input_tokens": None,
            "output_tokens": None,
        }

        text_parts = []
        skills_invoked = []
        tools_used = set()

        # Parse each line as separate JSON (NDJSON format)
        for line in json_str.strip().split("\n"):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(msg, dict):
                continue

            # Extract init message data
            if msg.get("type") == "system" and msg.get("subtype") == "init":
                result["model"] = msg.get("model")
                result["skills_available"] = msg.get("skills", [])
                result["mcp_servers"] = list(msg.get("mcp_servers", {}).keys()) if isinstance(msg.get("mcp_servers"), dict) else msg.get("mcp_servers", [])

            # Extract text and tool usage from assistant messages
            if msg.get("type") == "assistant":
                for content in msg.get("message", {}).get("content", []):
                    if isinstance(content, dict):
                        if content.get("type") == "text":
                            text = content.get("text", "").strip()
                            if text:
                                text_parts.append(text)
                        elif content.get("type") == "tool_use":
                            tool_name = content.get("name", "")
                            if tool_name:
                                tools_used.add(tool_name)
                            # Check if it's a Skill invocation
                            if tool_name == "Skill":
                                skill_input = content.get("input", {})
                                skill_name = skill_input.get("skill", "")
                                if skill_name:
                                    skills_invoked.append(skill_name)

            # Extract result message data (duration, cost, tokens)
            if msg.get("type") == "result":
                result["duration_ms"] = msg.get("duration_ms")
                result["num_turns"] = msg.get("num_turns")
                result["total_cost_usd"] = msg.get("total_cost_usd")
                usage = msg.get("usage", {})
                result["input_tokens"] = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                result["output_tokens"] = usage.get("output_tokens")

        result["output_text"] = "\n\n".join(text_parts)
        result["skills_invoked"] = skills_invoked
        result["tools_used"] = list(tools_used)

        return result

    def run_claude(
        self,
        env_dir: Path,
        prompt: str,
        mcp_config_path: Path | None = None,
        allowed_tools: list[str] | None = None,
    ) -> tuple[dict, bool, str | None, str]:
        """Run Claude Code with isolated config and capture output.

        Returns: (parsed_output, success, error, raw_json)
        """
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(env_dir / ".claude")

        cmd = [
            "claude",
            "--print",
            "--verbose",
            "--output-format", "stream-json",
        ]

        # Use allowed_tools if specified, otherwise skip all permissions
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])
            # Auto-deny disallowed tools instead of waiting for permission
            cmd.extend(["--permission-mode", "dontAsk"])
        else:
            cmd.append("--dangerously-skip-permissions")

        # Add MCP config if provided
        if mcp_config_path:
            cmd.extend(["--mcp-config", str(mcp_config_path)])

        cmd.extend(["-p", prompt])

        try:
            result = subprocess.run(
                cmd,
                cwd=env_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )

            # Parse JSON output (save raw for debugging)
            raw_json = result.stdout
            parsed = self._parse_json_output(raw_json)

            # Include stderr if there's an error
            if result.stderr:
                parsed["output_text"] += f"\n\n[stderr]\n{result.stderr}"

            return parsed, result.returncode == 0, None, raw_json
        except subprocess.TimeoutExpired as e:
            # Capture partial output on timeout (stdout/stderr are bytes)
            raw_json = e.stdout.decode("utf-8") if e.stdout else ""
            stderr = e.stderr.decode("utf-8") if e.stderr else ""
            parsed = self._parse_json_output(raw_json) if raw_json else {}
            if stderr:
                parsed["output_text"] = parsed.get("output_text", "") + f"\n\n[stderr]\n{stderr}"
            error_msg = "Timeout after 5 minutes (possibly waiting for tool approval?)"
            return parsed, False, error_msg, raw_json
        except Exception as e:
            return {}, False, str(e), ""

    def run_scenario(
        self,
        scenario: Scenario,
        skill_set: SkillSet,
        run_dir: Path,
    ) -> RunResult:
        """Run a single scenario with a skill set."""
        env_dir, mcp_config_path = self.prepare_environment(
            scenario_dir=scenario.path,
            context_dir=scenario.context_dir,
            skills=skill_set.skills,
            mcp_servers=skill_set.mcp_servers if skill_set.mcp_servers else None,
        )

        parsed, success, error, raw_json = self.run_claude(
            env_dir,
            scenario.prompt,
            mcp_config_path,
            skill_set.allowed_tools if skill_set.allowed_tools else None,
        )

        output_dir = run_dir / scenario.name / skill_set.name
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "output.md").write_text(parsed.get("output_text", ""))
        (output_dir / "raw.jsonl").write_text(raw_json)

        # Save metadata
        metadata = {
            "success": success,
            "skills_invoked": parsed.get("skills_invoked", []),
            "skills_available": parsed.get("skills_available", []),
            "tools_used": parsed.get("tools_used", []),
            "mcp_servers": parsed.get("mcp_servers", []),
            "model": parsed.get("model"),
            "duration_ms": parsed.get("duration_ms"),
            "num_turns": parsed.get("num_turns"),
            "total_cost_usd": parsed.get("total_cost_usd"),
            "input_tokens": parsed.get("input_tokens"),
            "output_tokens": parsed.get("output_tokens"),
        }
        if error:
            metadata["error"] = error
        (output_dir / "metadata.yaml").write_text(
            yaml.dump(metadata, default_flow_style=False, sort_keys=False)
        )

        # Copy modified context (excluding .claude, caches, .env) to preserve changes
        context_output = output_dir / "context"
        exclude_names = {".claude", ".cache", "Caches", ".env"}

        def ignore_patterns(directory: str, contents: list[str]) -> list[str]:
            """Ignore caches, .env, and other excluded items."""
            ignored = []
            for name in contents:
                if name in exclude_names:
                    ignored.append(name)
                elif directory.endswith("Library") and name == "Caches":
                    ignored.append(name)
            return ignored

        for item in env_dir.iterdir():
            if item.name not in exclude_names:
                dest = context_output / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, ignore=ignore_patterns)
                else:
                    context_output.mkdir(parents=True, exist_ok=True)
                    shutil.copy(item, dest)

        self._generate_transcript(env_dir, output_dir, scenario.name, skill_set.name)
        shutil.rmtree(env_dir, ignore_errors=True)

        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output=parsed.get("output_text", ""),
            success=success,
            error=error,
            skills_invoked=parsed.get("skills_invoked", []),
            tools_used=parsed.get("tools_used", []),
        )

    def run_parallel(
        self,
        tasks: list[RunTask],
        max_workers: int = 4,
        progress_callback: Callable[[RunTask, RunResult], None] | None = None,
    ) -> list[RunResult]:
        """Run multiple tasks in parallel.

        Args:
            tasks: List of RunTask objects to execute
            max_workers: Maximum number of concurrent workers
            progress_callback: Optional callback called after each task completes

        Returns:
            List of RunResult objects (order may differ from input)
        """
        results: list[RunResult] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._run_task, task): task for task in tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    if progress_callback:
                        progress_callback(task, result)
                except Exception as e:
                    # Create failure result for unexpected errors
                    result = RunResult(
                        scenario_name=task.scenario.name,
                        skill_set_name=task.skill_set.name,
                        output="",
                        success=False,
                        error=f"Unexpected error: {e}",
                    )
                    results.append(result)
                    if progress_callback:
                        progress_callback(task, result)

        return results

    def _run_task(self, task: RunTask) -> RunResult:
        """Run a single task (used by run_parallel)."""
        return self.run_scenario(task.scenario, task.skill_set, task.run_dir)
