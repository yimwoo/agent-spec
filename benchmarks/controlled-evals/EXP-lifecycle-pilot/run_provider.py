"""Run one isolated provider cell and capture raw execution provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentspec.eval import effective_evaluation_limits, load_evaluation_manifest


PILOT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PILOT_ROOT.parents[2]
DEFAULT_MANIFEST = PILOT_ROOT / "manifest.yml"
PROTOCOL_FAILURE_RETURN_CODE = 125


@dataclass(frozen=True)
class ProcessResult:
    """Captured provider process result with watchdog provenance."""

    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    termination_signal: str | None


def run_cell(
    provider: str,
    condition: str,
    workspace: Path,
    output_dir: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> int:
    """Execute one provider cell without interpreting its result."""

    manifest = load_evaluation_manifest(manifest_path)
    prompt_path = _prompt_path(provider, condition)
    command = _provider_command(provider, condition, workspace, output_dir, manifest)
    output_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC)
    started = time.monotonic()
    process = _run_process(
        command,
        cwd=workspace,
        prompt=prompt_path.read_text(encoding="utf-8"),
        timeout_seconds=float(manifest["limits"]["max_duration_seconds"]),
    )
    completed_at = datetime.now(UTC)
    duration = time.monotonic() - started
    usage = _extract_usage(provider, process.stdout)
    cost_usd = _extract_cost_usd(provider, process.stdout)
    provider_failure = _provider_failure(provider, process.stdout)
    limit_outcomes = _evaluate_limit_outcomes(
        manifest,
        provider=provider,
        usage=usage,
        cost_usd=cost_usd,
        duration_seconds=duration,
        retries=0,
        timed_out=process.timed_out,
    )
    stop_reason = _stop_reason(
        process.return_code,
        process.timed_out,
        limit_outcomes,
        provider_failure=provider_failure,
    )
    runner_return_code = process.return_code
    if process.timed_out:
        runner_return_code = 124
    elif process.return_code != 0 or provider_failure:
        runner_return_code = process.return_code or 1
    elif _blocking_limit_outcomes(limit_outcomes):
        runner_return_code = PROTOCOL_FAILURE_RETURN_CODE
    (output_dir / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (output_dir / "stderr.log").write_text(process.stderr, encoding="utf-8")
    (output_dir / "execution.json").write_text(
        json.dumps(
            {
                "schema": "agentspec.provider_execution.v1",
                "experiment_id": manifest["id"],
                "provider": provider,
                "condition": condition,
                "workspace": str(workspace),
                "prompt": str(prompt_path.relative_to(REPOSITORY_ROOT)),
                "manifest": str(manifest_path.resolve().relative_to(REPOSITORY_ROOT)),
                "manifest_sha256": _sha256(manifest_path),
                "command": command,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
                "duration_seconds": round(duration, 3),
                "provider_return_code": process.return_code,
                "provider_status": (
                    "failed" if process.return_code != 0 or provider_failure else "completed"
                ),
                "provider_failure": provider_failure,
                "runner_return_code": runner_return_code,
                "return_code": runner_return_code,
                "stop_reason": stop_reason,
                "termination_signal": process.termination_signal,
                "usage": usage,
                "cost_usd": cost_usd,
                "effective_limits": effective_evaluation_limits(manifest, provider),
                "limit_outcomes": limit_outcomes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return runner_return_code


def _provider_command(
    provider: str,
    condition: str,
    workspace: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> list[str]:
    provider_config = _provider_config(manifest, provider)
    model = str(provider_config["model"])
    if provider == "codex":
        command = [
            "codex",
            "exec",
            "--model",
            model,
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
            model,
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
        ]
        budget = provider_config.get("budget")
        if isinstance(budget, dict) and budget.get("enforcement") == "provider":
            command.extend(["--max-budget-usd", str(budget["max_cost_usd"])])
        if condition == "with-agentspec":
            command.extend(["--plugin-dir", str(REPOSITORY_ROOT / "agentspec-claude-plugin")])
        return command
    raise ValueError(f"Unsupported provider: {provider}")


def _provider_config(manifest: dict[str, Any], provider: str) -> dict[str, Any]:
    for item in manifest.get("providers", []):
        if isinstance(item, dict) and item.get("id") == provider:
            return item
    raise ValueError(f"Manifest does not define provider: {provider}")


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    prompt: str,
    timeout_seconds: float,
    termination_grace_seconds: float = 2.0,
) -> ProcessResult:
    """Run one provider command and terminate its process group at the deadline."""

    process = subprocess.Popen(  # pylint: disable=consider-using-with
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=os.name != "nt",
    )
    timed_out = False
    termination_signal: str | None = None
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        termination_signal = _terminate_process(process, force=False)
        try:
            stdout, stderr = process.communicate(timeout=termination_grace_seconds)
        except subprocess.TimeoutExpired:
            termination_signal = _terminate_process(process, force=True)
            stdout, stderr = process.communicate()
        stderr = _append_line(
            stderr,
            f"Provider execution exceeded {timeout_seconds:g} seconds.",
        )
    return ProcessResult(
        return_code=int(process.returncode if process.returncode is not None else 124),
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        termination_signal=termination_signal,
    )


def _terminate_process(process: subprocess.Popen[str], *, force: bool) -> str:
    if os.name != "nt":
        sig = signal.SIGKILL if force else signal.SIGTERM
        signal_name = "SIGKILL" if force else "SIGTERM"
        try:
            os.killpg(process.pid, sig)
            return signal_name
        except ProcessLookupError:
            return signal_name
    if force:
        process.kill()
        return "kill"
    process.terminate()
    return "terminate"


def _extract_usage(provider: str, stdout: str) -> dict[str, int] | None:
    """Extract final provider token usage without estimating missing fields."""

    if provider == "codex":
        usage: dict[str, Any] | None = None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("type") == "turn.completed":
                candidate = event.get("usage")
                if isinstance(candidate, dict):
                    usage = candidate
        return _normalize_usage(usage)
    if provider == "claude":
        payload = _json_object(stdout)
        candidate = payload.get("usage") if payload else None
        return _normalize_usage(candidate if isinstance(candidate, dict) else None, claude=True)
    raise ValueError(f"Unsupported provider: {provider}")


def _normalize_usage(value: dict[str, Any] | None, *, claude: bool = False) -> dict[str, int] | None:
    if value is None:
        return None
    input_tokens = _non_negative_int(value.get("input_tokens"))
    output_tokens = _non_negative_int(value.get("output_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    cached = _non_negative_int(value.get("cached_input_tokens"))
    if claude:
        cache_read = _non_negative_int(value.get("cache_read_input_tokens")) or 0
        cache_creation = _non_negative_int(value.get("cache_creation_input_tokens")) or 0
        cached = cache_read + cache_creation
        input_tokens += cached
    cached = cached or 0
    return {
        "input": input_tokens,
        "cached": cached,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
    }


def _extract_cost_usd(provider: str, stdout: str) -> float | None:
    if provider != "claude":
        return None
    payload = _json_object(stdout)
    if payload is None:
        return None
    value = payload.get("total_cost_usd")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _provider_failure(provider: str, stdout: str) -> str | None:
    """Detect provider-level failures that are not reflected in process exit status."""

    if provider == "claude":
        payload = _json_object(stdout)
        if payload and payload.get("is_error") is True:
            status = payload.get("api_error_status")
            suffix = f" (api_error_status={status})" if status is not None else ""
            return f"Claude result reported is_error=true{suffix}."
        return None
    if provider == "codex":
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type == "turn.failed":
                error = event.get("error")
                message = error.get("message") if isinstance(error, dict) else error
                return f"Codex emitted turn.failed: {message or 'unknown error'}"
            if event_type == "error":
                return f"Codex emitted error: {event.get('message') or 'unknown error'}"
        return None
    raise ValueError(f"Unsupported provider: {provider}")


def _json_object(value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _evaluate_limit_outcomes(
    manifest: dict[str, Any],
    *,
    provider: str,
    usage: dict[str, int] | None,
    cost_usd: float | None,
    duration_seconds: float,
    retries: int,
    timed_out: bool,
) -> dict[str, dict[str, Any]]:
    """Evaluate observed execution against every declared limit policy."""

    limits = manifest["limits"]
    policies = limits.get("policies")
    if not isinstance(policies, dict):
        policies = _legacy_limit_policies()
    observed = {
        "max_duration_seconds": duration_seconds,
        "max_tokens": usage.get("total") if usage else None,
        "max_retries": retries,
    }
    outcomes = {
        limit_id: _limit_outcome(
            limit_id,
            maximum=limits[limit_id],
            policy=policies[limit_id],
            observed=value,
            forced_exceeded=limit_id == "max_duration_seconds" and timed_out,
        )
        for limit_id, value in observed.items()
    }
    budget = _provider_config(manifest, provider).get("budget")
    if isinstance(budget, dict):
        outcomes["max_cost_usd"] = _limit_outcome(
            "max_cost_usd",
            maximum=budget.get("max_cost_usd"),
            policy=budget,
            observed=cost_usd,
        )
    return outcomes


def _legacy_limit_policies() -> dict[str, dict[str, Any]]:
    return {
        "max_duration_seconds": {
            "unit": "seconds",
            "enforcement": "runner",
            "observation_required": True,
        },
        "max_tokens": {
            "unit": "tokens",
            "enforcement": "post_run",
            "observation_required": True,
        },
        "max_retries": {
            "unit": "attempts",
            "enforcement": "runner",
            "observation_required": True,
        },
    }


def _limit_outcome(
    limit_id: str,
    *,
    maximum: Any,
    policy: dict[str, Any],
    observed: int | float | None,
    forced_exceeded: bool = False,
) -> dict[str, Any]:
    enforcement = policy["enforcement"]
    required = bool(policy["observation_required"])
    if enforcement == "unavailable":
        status = "unavailable"
    elif observed is None:
        status = "unobserved_required" if required else "unavailable"
    elif forced_exceeded or (isinstance(maximum, (int, float)) and observed > maximum):
        status = "exceeded"
    else:
        status = "passed"
    return {
        "id": limit_id,
        "limit": maximum,
        "unit": policy["unit"],
        "enforcement": enforcement,
        "observation_required": required,
        "observed": observed,
        "status": status,
    }


def _blocking_limit_outcomes(outcomes: dict[str, dict[str, Any]]) -> list[str]:
    return [
        limit_id
        for limit_id, outcome in outcomes.items()
        if outcome.get("status") in {"exceeded", "unobserved_required", "unsupported"}
    ]


def _stop_reason(
    provider_return_code: int,
    timed_out: bool,
    outcomes: dict[str, dict[str, Any]],
    *,
    provider_failure: str | None = None,
) -> str:
    if timed_out:
        return "duration_exceeded"
    if provider_return_code != 0 or provider_failure:
        return "provider_failed"
    blocking = _blocking_limit_outcomes(outcomes)
    if blocking:
        return f"{blocking[0]}_{outcomes[blocking[0]]['status']}"
    return "completed"


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _append_line(value: str, line: str) -> str:
    return f"{value.rstrip()}\n{line}\n" if value else f"{line}\n"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _prompt_path(provider: str, condition: str) -> Path:
    if condition == "control":
        return PILOT_ROOT / "prompts" / "control.txt"
    if condition != "with-agentspec":
        raise ValueError(f"Unsupported condition: {condition}")
    return PILOT_ROOT / "prompts" / f"{provider}-with-agentspec.txt"


def main() -> int:
    """Run one manifest-pinned provider cell from command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("codex", "claude"))
    parser.add_argument("--condition", required=True, choices=("control", "with-agentspec"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    return run_cell(
        args.provider,
        args.condition,
        args.workspace.resolve(),
        args.output_dir.resolve(),
        args.manifest.resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
