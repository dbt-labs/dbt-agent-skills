"""Tests for skill_eval runner."""

from pathlib import Path

from skill_eval.runner import Runner


def test_runner_creates_output_directory(tmp_path: Path) -> None:
    """Runner creates timestamped output directory."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    assert run_dir.exists()
    assert run_dir.parent == evals_dir / "runs"
    assert len(run_dir.name) == 15  # e.g., 2025-01-15-1030


def test_runner_prepares_isolated_environment(tmp_path: Path) -> None:
    """Runner creates isolated Claude config with only specified skills."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "variants" / "debug").mkdir(parents=True)
    (evals_dir / "variants" / "debug" / "v1.md").write_text("# Debug skill v1")

    runner = Runner(evals_dir=evals_dir)
    env_dir = runner.prepare_environment(
        context_dir=None,
        skills=["debug/v1.md"],
    )

    claude_dir = env_dir / ".claude"
    assert claude_dir.exists()
    skill_file = claude_dir / "skills" / "debug" / "v1.md"
    assert skill_file.exists()
    assert "Debug skill v1" in skill_file.read_text()
