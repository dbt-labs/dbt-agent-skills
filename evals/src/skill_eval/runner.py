"""Runner for executing scenarios against skill variants."""

import filecmp
import json
import os
import select
import shutil
import subprocess
import tempfile
import time
import urllib.request

from skill_eval.logging import logger
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


def _find_changed_files(
    original_dir: Path,
    modified_dir: Path,
    exclude_names: set[str],
) -> list[Path]:
    """Find files that changed or were added in modified_dir compared to original_dir.

    Uses filecmp for efficient stat-based comparison.
    Returns list of relative paths to changed/new files.
    """
    changed: list[Path] = []

    def _compare_dirs(dcmp: filecmp.dircmp, rel_path: Path = Path(".")) -> None:
        # Files that differ
        for name in dcmp.diff_files:
            if name not in exclude_names:
                changed.append(rel_path / name)

        # Files only in modified_dir (new files)
        for name in dcmp.right_only:
            if name not in exclude_names:
                item = modified_dir / rel_path / name
                if item.is_file():
                    changed.append(rel_path / name)
                elif item.is_dir():
                    # New directory - add all files within
                    for f in item.rglob("*"):
                        if f.is_file() and f.name not in exclude_names:
                            changed.append(f.relative_to(modified_dir))

        # Recurse into subdirectories
        for name, sub_dcmp in dcmp.subdirs.items():
            if name not in exclude_names:
                _compare_dirs(sub_dcmp, rel_path / name)

    # Handle case where original_dir doesn't exist (everything is new)
    if not original_dir or not original_dir.exists():
        for f in modified_dir.rglob("*"):
            if f.is_file() and f.name not in exclude_names:
                changed.append(f.relative_to(modified_dir))
        return changed

    dcmp = filecmp.dircmp(original_dir, modified_dir, ignore=list(exclude_names))
    _compare_dirs(dcmp)
    return changed


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
        self, env_dir: Path, output_dir: Path, scenario_name: str, skill_set_name: str, log=None
    ) -> None:
        """Generate HTML transcript from Claude's native session file."""
        import contextlib
        import io

        log = log or logger
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

            # Capture stdout/stderr from the library
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                generate_html(session_file, transcript_dir)

            # Log any captured output at debug level
            for line in stdout_capture.getvalue().strip().split("\n"):
                if line:
                    log.debug(f"transcript: {line}")
            for line in stderr_capture.getvalue().strip().split("\n"):
                if line:
                    log.debug(f"transcript: {line}")

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
            log.warning(f"Transcript generation failed: {e}")

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

        # Copy .env from scenario dir if it exists
        env_file = scenario_dir / ".env"
        if env_file.exists():
            shutil.copy(env_file, env_dir / ".env")

        # Write MCP server config if provided
        mcp_config_path = None
        if mcp_servers:
            mcp_config_path = claude_dir / "mcp-servers.json"
            mcp_config_path.write_text(json.dumps({"mcpServers": mcp_servers}, indent=2))

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

    def _read_output_line(
        self, proc: subprocess.Popen, timeout: float = 1.0
    ) -> str | None:
        """Read a single line from process stdout if available."""
        if not proc.stdout:
            return None
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready:
            return None
        return proc.stdout.readline() or None

    def _log_progress(self, line: str, elapsed: float, log=None) -> None:
        """Log progress from a JSON line (tool calls, etc.)."""
        log = log or logger
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return

        if msg.get("type") != "assistant":
            return

        for content in msg.get("message", {}).get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") != "tool_use":
                continue

            tool_name = content.get("name", "unknown")
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)

            # Show skill name when Skill tool is invoked
            if tool_name == "Skill":
                skill_name = content.get("input", {}).get("skill", "unknown")
                log.debug(f"[{elapsed_min}:{elapsed_sec:02d}] skill: {skill_name}")
            else:
                log.debug(f"[{elapsed_min}:{elapsed_sec:02d}] tool: {tool_name}")

    def _drain_remaining_output(
        self,
        proc: subprocess.Popen,
        stdout_lines: list[str],
        stderr_lines: list[str],
    ) -> None:
        """Read any remaining output from process after it finishes."""
        if proc.stdout:
            remaining = proc.stdout.read()
            if remaining:
                stdout_lines.append(remaining)
        if proc.stderr:
            remaining = proc.stderr.read()
            if remaining:
                stderr_lines.append(remaining)

    def _load_dot_env(self, env_file: Path) -> dict[str, str]:
        """Parse a .env file into a dict. Skips comments and blank lines."""
        env_vars: dict[str, str] = {}
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            if _:
                env_vars[key.strip()] = value.strip()
        return env_vars

    def run_claude(
        self,
        env_dir: Path,
        prompt: str,
        mcp_config_path: Path | None = None,
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
        stall_timeout: int = 60,
        ctx_logger=None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[dict, bool, str | None, str]:
        """Run Claude Code with isolated config and capture output.

        Args:
            env_dir: Directory to run Claude in
            prompt: The prompt to send
            mcp_config_path: Optional path to MCP config
            allowed_tools: Optional list of allowed tools
            timeout: Maximum total runtime in seconds (default: 600 = 10 min)
            stall_timeout: Kill if no output for this many seconds (default: 60)
            ctx_logger: Optional logger with bound context (scenario, skill_set)
            extra_env: Optional extra environment variables (e.g. from .env file)

        Returns: (parsed_output, success, error, raw_json)
        """
        log = ctx_logger or logger
        env = os.environ.copy()
        env.update(extra_env or {})
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
            proc = subprocess.Popen(
                cmd,
                cwd=env_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            start_time = time.time()
            last_output_time = start_time
            error_msg = None

            # Read output with stall detection
            while proc.poll() is None:
                elapsed = time.time() - start_time
                stall_duration = time.time() - last_output_time

                # Check total timeout
                if elapsed > timeout:
                    proc.kill()
                    error_msg = f"Timeout after {timeout // 60} minutes"
                    log.warning(error_msg)
                    break

                # Check stall timeout
                if stall_duration > stall_timeout:
                    proc.kill()
                    error_msg = f"Stalled for {stall_timeout}s (possibly waiting for approval)"
                    log.warning(error_msg)
                    break

                # Check for available output
                line = self._read_output_line(proc, timeout=1.0)
                if not line:
                    continue

                stdout_lines.append(line)
                last_output_time = time.time()
                self._log_progress(line, elapsed, log)

            # Read any remaining output
            self._drain_remaining_output(proc, stdout_lines, stderr_lines)

            raw_json = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            parsed = self._parse_json_output(raw_json) if raw_json else {}

            if stderr:
                parsed["output_text"] = parsed.get("output_text", "") + f"\n\n[stderr]\n{stderr}"

            if error_msg:
                return parsed, False, error_msg, raw_json

            return parsed, proc.returncode == 0, None, raw_json

        except Exception as e:
            return {}, False, str(e), ""

    def run_scenario(
        self,
        scenario: Scenario,
        skill_set: SkillSet,
        run_dir: Path,
    ) -> RunResult:
        """Run a single scenario with a skill set."""
        # Bind context for logging
        ctx_logger = logger.bind(scenario=scenario.name, skill_set=skill_set.name)
        ctx_logger.info("Starting")

        env_dir, mcp_config_path = self.prepare_environment(
            scenario_dir=scenario.path,
            context_dir=scenario.context_dir,
            skills=skill_set.skills,
            mcp_servers=skill_set.mcp_servers if skill_set.mcp_servers else None,
        )

        # Load .env vars for setup commands and Claude
        dot_env_vars: dict[str, str] = {}
        dot_env_path = env_dir / ".env"
        if dot_env_path.exists():
            dot_env_vars = self._load_dot_env(dot_env_path)

        # Run setup commands before Claude
        if skill_set.setup:
            setup_env = {**os.environ, **dot_env_vars}
            for cmd in skill_set.setup:
                ctx_logger.info(f"Setup: {cmd}")
                result = subprocess.run(
                    cmd, shell=True, cwd=env_dir, env=setup_env, capture_output=True, text=True
                )
                if result.returncode != 0:
                    stderr = result.stderr.strip()
                    error_msg = f"Setup command failed: {cmd}\n{stderr}"
                    ctx_logger.error(error_msg)
                    output_dir = run_dir / scenario.name / skill_set.name
                    output_dir.mkdir(parents=True, exist_ok=True)
                    (output_dir / "output.md").write_text("")
                    (output_dir / "raw.jsonl").write_text("")
                    metadata = {"success": False, "error": error_msg}
                    (output_dir / "metadata.yaml").write_text(
                        yaml.dump(metadata, default_flow_style=False, sort_keys=False)
                    )
                    shutil.rmtree(env_dir, ignore_errors=True)
                    return RunResult(
                        scenario_name=scenario.name,
                        skill_set_name=skill_set.name,
                        output="",
                        success=False,
                        error=error_msg,
                    )

        # Combine base prompt with skill set's extra_prompt (if any)
        prompt = scenario.prompt
        if skill_set.extra_prompt:
            prompt = f"{prompt}\n\n{skill_set.extra_prompt}"

        parsed, success, error, raw_json = self.run_claude(
            env_dir,
            prompt,
            mcp_config_path,
            skill_set.allowed_tools if skill_set.allowed_tools else None,
            ctx_logger=ctx_logger,
            extra_env=dot_env_vars if dot_env_vars else None,
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

        # Copy only files that changed (excluding .claude, caches, .env)
        changes_output = output_dir / "changes"
        exclude_names = {".claude", ".cache", "Caches", ".env"}

        changed_files = _find_changed_files(
            scenario.context_dir, env_dir, exclude_names
        )

        for rel_path in changed_files:
            src = env_dir / rel_path
            dest = changes_output / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

        self._generate_transcript(env_dir, output_dir, scenario.name, skill_set.name, ctx_logger)
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
