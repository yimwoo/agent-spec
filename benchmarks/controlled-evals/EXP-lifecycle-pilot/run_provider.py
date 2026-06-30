"""Run one isolated provider cell and capture raw execution provenance."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


PILOT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PILOT_ROOT.parents[2]


def run_cell(provider: str, condition: str, workspace: Path, output_dir: Path) -> int:
    """Execute one provider cell without interpreting its result."""

    prompt_path = _prompt_path(provider, condition)
    command = _provider_command(provider, condition, workspace, output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC)
    started = time.monotonic()
    return_code = 124
    stdout = ""
    stderr = ""
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            input=prompt_path.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
            timeout=600,
        )
        return_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr) + "\nProvider execution exceeded 600 seconds."
    completed_at = datetime.now(UTC)
    duration = time.monotonic() - started
    (output_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (output_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    (output_dir / "execution.json").write_text(
        json.dumps(
            {
                "provider": provider,
                "condition": condition,
                "workspace": str(workspace),
                "prompt": str(prompt_path.relative_to(REPOSITORY_ROOT)),
                "command": command,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
                "duration_seconds": round(duration, 3),
                "return_code": return_code,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return return_code


def _provider_command(provider: str, condition: str, workspace: Path, output_dir: Path) -> list[str]:
    if provider == "codex":
        command = [
            "codex",
            "exec",
            "--model",
            "gpt-5.5",
            "--sandbox",
            "workspace-write",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--cd",
            str(workspace),
            "--output-last-message",
            str(output_dir / "last-message.txt"),
        ]
        if condition == "with-agentspec":
            command.append("--dangerously-bypass-hook-trust")
        return [*command, "-"]
    if provider == "claude":
        command = [
            "claude",
            "--print",
            "--model",
            "claude-opus-4-8",
            "--effort",
            "high",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--setting-sources",
            "project,local",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            "Read,Edit,Write,Bash",
            "--max-budget-usd",
            "2.00",
        ]
        if condition == "with-agentspec":
            command.extend(["--plugin-dir", str(REPOSITORY_ROOT / "agentspec-claude-plugin")])
        return command
    raise ValueError(f"Unsupported provider: {provider}")


def _prompt_path(provider: str, condition: str) -> Path:
    if condition == "control":
        return PILOT_ROOT / "prompts" / "control.txt"
    if condition != "with-agentspec":
        raise ValueError(f"Unsupported condition: {condition}")
    return PILOT_ROOT / "prompts" / f"{provider}-with-agentspec.txt"


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("codex", "claude"))
    parser.add_argument("--condition", required=True, choices=("control", "with-agentspec"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    return run_cell(
        args.provider,
        args.condition,
        args.workspace.resolve(),
        args.output_dir.resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
