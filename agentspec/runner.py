"""External runner package, result, and evidence helpers for AgentSpec runs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .errors import (
    RunnerResultInvalidError,
    RunnerStartFailedError,
    RunnerTimeoutError,
)
from .review import research_acceptance_evidence_template, validate_research_acceptance_evidence
from .policy import redact_sensitive_text
from .run import (
    append_run_event,
    controller_observed_touched_paths,
    load_run_state,
    step_run,
    validate_run_id,
)


RUNNER_PACKAGE_SCHEMA = "agentspec.runner_package.v0"
RUNNER_RESULT_SCHEMA = "agentspec.runner_result.v0"
RUNNER_EVIDENCE_SCHEMA = "agentspec.runner_evidence.v0"
RUNNER_DEMO_SCHEMA = "agentspec.runner_demo.v0"
RUNNER_EXEC_SCHEMA = "agentspec.runner_exec.v0"
ALLOWED_RUNNERS = {"generic", "codex", "claude"}
ALLOWED_TEST_STATUSES = {"not_run", "passed", "failed"}
ALLOWED_REVIEWER_MODES = {"deterministic", "model", "auto"}
ALLOWED_EVIDENCE_ARTIFACT_KINDS = {
    "console_log",
    "dom_snapshot",
    "navigation_trace",
    "network_log",
    "screenshot",
    "trace",
    "video",
    "other",
}


def package_run(
    root: Path,
    context_pack: Path | None = None,
    *,
    runner: str = "generic",
    run_id: str | None = None,
    executor_output: str | None = None,
    touched_paths: list[str] | None = None,
    reported_touched_paths: list[str] | None = None,
    test_status: str = "not_run",
    reviewer_mode: str | None = None,
    acceptance_evidence: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    task_type: str | None = None,
    order: str = "newest",
    max_iterations: int | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a runner package from the current AgentSpec run step.

    Args:
        root: AgentSpec project root.
        context_pack: Optional context-pack selector for a new run.
        runner: Runner adapter name.
        run_id: Optional run id to start or resume.
        executor_output: Optional executor output to submit first.
        touched_paths: Paths reported by the executor.
        reported_touched_paths: Paths reported before controller observation.
        test_status: Verification status for submitted output.
        reviewer_mode: Optional reviewer mode override.
        acceptance_evidence: Optional research-mode acceptance evidence.
        evidence: Optional runner evidence payload.
        task_type: Optional task-type filter.
        order: Ready-task ordering strategy.
        max_iterations: Optional iteration cap.
        run_dir: Optional alternate run-state directory.

    Returns:
        A runner package containing execution instructions and report-back
        schema.
    """

    if runner not in ALLOWED_RUNNERS:
        raise ValueError(f"Unknown runner: {runner}. Expected one of {sorted(ALLOWED_RUNNERS)}.")

    step = step_run(
        root,
        context_pack,
        run_id=run_id,
        executor_output=executor_output,
        touched_paths=touched_paths or [],
        reported_touched_paths=reported_touched_paths,
        test_status=test_status,
        reviewer_mode=reviewer_mode,
        acceptance_evidence=acceptance_evidence,
        evidence=evidence,
        task_type=task_type,
        order=order,
        max_iterations=max_iterations,
        run_dir=run_dir,
    )
    return build_runner_package(step, runner=runner, run_dir=_run_dir_arg(root, run_dir))


def submit_runner_result(
    root: Path,
    run_id: str,
    result: dict[str, Any],
    *,
    runner: str = "generic",
    reviewer_mode: str | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate and submit a runner result back into the AgentSpec loop."""

    root = root.resolve()
    validate_run_id(run_id)
    try:
        parsed = parse_runner_result(result)
    except ValueError as exc:
        try:
            state = load_run_state(root, run_id, run_dir=run_dir)
        except FileNotFoundError as file_exc:
            raise exc from file_exc
        raise _record_runner_result_rejected(
            root,
            run_id,
            exc,
            runner=runner,
            state=state,
            run_dir=run_dir,
        ) from exc
    state = load_run_state(root, run_id, run_dir=run_dir)
    if state.get("mode") == "research" and parsed["test_status"] == "passed" and parsed.get("acceptance_evidence") is None:
        error = ValueError("Research-mode passed runner results require acceptance_evidence.")
        raise _record_runner_result_rejected(
            root,
            run_id,
            error,
            runner=runner,
            state=state,
            run_dir=run_dir,
        ) from error
    mode = reviewer_mode or parsed.get("reviewer_mode")
    runner_reported_paths = list(parsed["touched_paths"])
    observed_available, observed_paths = controller_observed_touched_paths(
        root,
        state.get("controller_path_baseline"),
    )
    touched_paths = observed_paths if observed_available else runner_reported_paths
    return package_run(
        root,
        runner=runner,
        run_id=run_id,
        executor_output=str(parsed["executor_output"]),
        touched_paths=touched_paths,
        reported_touched_paths=runner_reported_paths if observed_available else None,
        test_status=str(parsed["test_status"]),
        reviewer_mode=mode if isinstance(mode, str) else None,
        acceptance_evidence=parsed.get("acceptance_evidence"),
        evidence=parsed.get("evidence"),
        run_dir=run_dir,
    )


def run_demo(
    root: Path,
    context_pack: Path | None = None,
    *,
    runner: str = "generic",
    run_id: str | None = None,
    executor_output: str = "Done. Acceptance criteria are met.",
    touched_paths: list[str] | None = None,
    test_status: str = "passed",
    reviewer_mode: str | None = None,
    task_type: str | None = None,
    order: str = "newest",
    max_iterations: int | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the package/result loop in-process for demos and smoke tests."""

    initial_package = package_run(
        root,
        context_pack,
        runner=runner,
        run_id=run_id,
        task_type=task_type,
        order=order,
        max_iterations=max_iterations,
        run_dir=run_dir,
    )
    actual_run_id = str(initial_package["run_id"])
    transcript: list[dict[str, Any]] = [{"kind": "package", "package": initial_package}]
    final_package = initial_package

    if initial_package.get("should_execute"):
        result = {
            "schema": RUNNER_RESULT_SCHEMA,
            "executor_output": executor_output,
            "touched_paths": touched_paths or _default_demo_touched_paths(initial_package),
            "test_status": test_status,
        }
        if reviewer_mode is not None:
            result["reviewer_mode"] = reviewer_mode
        transcript.append({"kind": "runner_result", "result": _redact_runner_result(result)})
        final_package = submit_runner_result(
            root,
            actual_run_id,
            result,
            runner=runner,
            reviewer_mode=reviewer_mode,
            run_dir=run_dir,
        )
        transcript.append({"kind": "package", "package": final_package})

    return {
        "schema": RUNNER_DEMO_SCHEMA,
        "runner": runner,
        "run_id": actual_run_id,
        "transcript": transcript,
        "final_package": final_package,
        "final_next_action": final_package.get("next_action"),
        "final_should_execute": final_package.get("should_execute"),
        "final_state": final_package.get("step", {}).get("state") if isinstance(final_package.get("step"), dict) else None,
    }


def execute_runner(
    root: Path,
    context_pack: Path | None = None,
    *,
    runner: str = "generic",
    command: list[str] | None = None,
    run_id: str | None = None,
    touched_paths: list[str] | None = None,
    test_status: str = "not_run",
    reviewer_mode: str | None = None,
    task_type: str | None = None,
    order: str = "newest",
    max_iterations: int | None = None,
    timeout_seconds: float | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute a local runner command and submit its captured result.

    Args:
        root: AgentSpec project root.
        context_pack: Optional context-pack selector for a new run.
        runner: Runner adapter name.
        command: Command arguments for the runner process.
        run_id: Optional run id to start or resume.
        touched_paths: Paths to report when controller observation is
            unavailable.
        test_status: Verification status to attach to successful execution.
        reviewer_mode: Optional reviewer mode override.
        task_type: Optional task-type filter.
        order: Ready-task ordering strategy.
        max_iterations: Optional iteration cap.
        timeout_seconds: Optional subprocess timeout.
        run_dir: Optional alternate run-state directory.

    Returns:
        Runner execution transcript and final package.
    """

    root = root.resolve()
    if command is not None and not command:
        raise ValueError("Runner command must not be empty.")
    if command is None and runner == "generic":
        raise ValueError("Runner generic has no default command. Pass --command or --command-json.")
    initial_package = package_run(
        root,
        context_pack,
        runner=runner,
        run_id=run_id,
        task_type=task_type,
        order=order,
        max_iterations=max_iterations,
        run_dir=run_dir,
    )
    actual_run_id = str(initial_package["run_id"])
    transcript: list[dict[str, Any]] = [{"kind": "package", "package": initial_package}]
    final_package = initial_package

    if initial_package.get("should_execute"):
        append_run_event(
            root,
            actual_run_id,
            {
                "kind": "runner_invocation_started",
                "runner": runner,
                "command": _runner_command_for_event(initial_package, command),
                "recovery_command": _runner_package_recovery_command(actual_run_id, runner),
            },
            run_dir=run_dir,
        )
        execution = _run_package_subprocess(
            root,
            initial_package,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        append_run_event(
            root,
            actual_run_id,
            _runner_invocation_finished_event(
                execution,
                runner=runner,
                run_id=actual_run_id,
            ),
            run_dir=run_dir,
        )
        transcript.append({"kind": "subprocess", "execution": _redact_execution(execution)})
        result = {
            "schema": RUNNER_RESULT_SCHEMA,
            "executor_output": _executor_output_from_subprocess(execution),
            "touched_paths": touched_paths if touched_paths is not None else execution.get("touched_paths", []),
            "test_status": "failed" if execution.get("returncode") not in {0, None} or execution.get("error") else test_status,
        }
        if reviewer_mode is not None:
            result["reviewer_mode"] = reviewer_mode
        transcript.append({"kind": "runner_result", "result": _redact_runner_result(result)})
        final_package = submit_runner_result(
            root,
            actual_run_id,
            result,
            runner=runner,
            reviewer_mode=reviewer_mode,
            run_dir=run_dir,
        )
        transcript.append({"kind": "package", "package": final_package})

    return {
        "schema": RUNNER_EXEC_SCHEMA,
        "runner": runner,
        "run_id": actual_run_id,
        "transcript": transcript,
        "final_package": final_package,
        "final_next_action": final_package.get("next_action"),
        "final_should_execute": final_package.get("should_execute"),
        "final_state": final_package.get("step", {}).get("state") if isinstance(final_package.get("step"), dict) else None,
    }


def _record_runner_result_rejected(
    root: Path,
    run_id: str,
    exc: ValueError,
    *,
    runner: str,
    state: dict[str, Any],
    run_dir: Path | None,
) -> RunnerResultInvalidError:
    error = RunnerResultInvalidError(
        str(exc),
        operation="run.result",
        recovery_command=_runner_package_recovery_command(run_id, runner),
        details={
            "mutation": "none",
            "run_id": run_id,
            "runner": runner,
        },
        type_name=type(exc).__name__,
    )
    append_run_event(
        root,
        run_id,
        {
            "kind": "runner_result_rejected",
            "iteration": state.get("iteration"),
            "runner": runner,
            "mutation": "none",
            "error": error.to_dict(),
            "recovery_command": error.recovery_command,
        },
        run_dir=run_dir,
    )
    return error


def _runner_invocation_finished_event(
    execution: dict[str, Any],
    *,
    runner: str,
    run_id: str,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "kind": "runner_invocation_finished",
        "runner": runner,
        "execution": _execution_event_summary(execution),
        "recovery_command": _runner_package_recovery_command(run_id, runner),
    }
    error = _runner_invocation_error(execution, runner=runner, run_id=run_id)
    if error is not None:
        event["error"] = error.to_dict()
    return event


def _runner_invocation_error(execution: dict[str, Any], *, runner: str, run_id: str):
    recovery_command = _runner_package_recovery_command(run_id, runner)
    details = {
        "run_id": run_id,
        "runner": runner,
        "mutation": "run_event_only",
    }
    if execution.get("timed_out"):
        return RunnerTimeoutError(
            str(execution.get("error") or "Runner command timed out."),
            operation="run.exec",
            recovery_command=recovery_command,
            details=details,
        )
    error = execution.get("error")
    if isinstance(error, str) and error:
        return RunnerStartFailedError(
            error,
            operation="run.exec",
            recovery_command=recovery_command,
            details=details,
        )
    return None


def _runner_command_for_event(package: dict[str, Any], command: list[str] | None) -> list[str]:
    argv = command if command is not None else list(package.get("execution", {}).get("argv") or [])
    return [
        redact_sensitive_text(item) if isinstance(item, str) else str(item)
        for item in argv
    ]


def _runner_package_recovery_command(run_id: str, runner: str) -> str:
    return f"aspec run package --runner {runner} --run-id {run_id} --json"


def _execution_event_summary(execution: dict[str, Any]) -> dict[str, Any]:
    summary = _redact_execution(execution)
    for key in ("stdout", "stderr", "error"):
        value = summary.get(key)
        if isinstance(value, str) and len(value) > 1000:
            summary[key] = f"{value[:1000]}... [truncated]"
    return summary


def parse_runner_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a runner result payload.

    Raises:
        ValueError: If the result schema, status, touched paths, or optional
            evidence payload is invalid.
    """

    if not isinstance(result, dict):
        raise ValueError("Runner result must be a JSON object.")
    schema = result.get("schema")
    if schema is not None and schema != RUNNER_RESULT_SCHEMA:
        raise ValueError(f"Runner result schema must be {RUNNER_RESULT_SCHEMA}.")

    executor_output = result.get("executor_output")
    if not isinstance(executor_output, str):
        raise ValueError("Runner result field executor_output must be a string.")

    touched_paths = result.get("touched_paths", [])
    if not isinstance(touched_paths, list) or not all(isinstance(path, str) for path in touched_paths):
        raise ValueError("Runner result field touched_paths must be a list of strings.")

    test_status = result.get("test_status", "not_run")
    if test_status not in ALLOWED_TEST_STATUSES:
        raise ValueError(f"Runner result field test_status must be one of {sorted(ALLOWED_TEST_STATUSES)}.")

    reviewer_mode = result.get("reviewer_mode")
    if reviewer_mode is not None and reviewer_mode not in ALLOWED_REVIEWER_MODES:
        raise ValueError(f"Runner result field reviewer_mode must be one of {sorted(ALLOWED_REVIEWER_MODES)}.")

    acceptance_evidence = result.get("acceptance_evidence")
    if acceptance_evidence is not None:
        acceptance_evidence = validate_research_acceptance_evidence(acceptance_evidence)

    evidence = result.get("evidence")
    if evidence is not None:
        evidence = validate_runner_evidence(evidence)

    return {
        "schema": schema or RUNNER_RESULT_SCHEMA,
        "executor_output": executor_output,
        "touched_paths": touched_paths,
        "test_status": test_status,
        "reviewer_mode": reviewer_mode,
        "acceptance_evidence": acceptance_evidence,
        "evidence": evidence,
    }


def runner_evidence_template() -> dict[str, Any]:
    """Return the expected runner evidence payload template."""

    return {
        "schema": RUNNER_EVIDENCE_SCHEMA,
        "artifact_kinds": sorted(ALLOWED_EVIDENCE_ARTIFACT_KINDS),
        "artifacts": [
            {
                "kind": "screenshot",
                "path": "<repo-relative-artifact-path>",
                "description": "<what this artifact proves>",
            }
        ],
        "verification_commands": [
            {
                "command": "<command>",
                "status": "<not_run|passed|failed>",
            }
        ],
        "notes": "<optional evidence notes>",
    }


def validate_runner_evidence(evidence: Any) -> dict[str, Any]:
    """Validate and normalize runner evidence artifacts and commands."""

    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a JSON object.")
    if evidence.get("schema") != RUNNER_EVIDENCE_SCHEMA:
        raise ValueError(f"evidence schema must be {RUNNER_EVIDENCE_SCHEMA}.")

    artifacts = evidence.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("evidence.artifacts must be a list.")
    normalized_artifacts = [_validate_evidence_artifact(item) for item in artifacts]

    verification_commands = evidence.get("verification_commands", [])
    if not isinstance(verification_commands, list):
        raise ValueError("evidence.verification_commands must be a list.")
    normalized_commands = [
        _validate_evidence_command(item)
        for item in verification_commands
    ]

    notes = evidence.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("evidence.notes must be a string when provided.")
    if not normalized_artifacts and not normalized_commands:
        raise ValueError("evidence requires at least one artifact or verification command.")

    normalized: dict[str, Any] = {
        "schema": RUNNER_EVIDENCE_SCHEMA,
        "artifacts": normalized_artifacts,
        "verification_commands": normalized_commands,
    }
    if notes is not None:
        normalized["notes"] = notes
    return normalized


def _validate_evidence_artifact(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("evidence.artifacts entries must be JSON objects.")
    kind = item.get("kind")
    if kind not in ALLOWED_EVIDENCE_ARTIFACT_KINDS:
        raise ValueError(
            "evidence.artifacts entries require kind to be one of "
            f"{sorted(ALLOWED_EVIDENCE_ARTIFACT_KINDS)}."
        )
    path = item.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("evidence.artifacts entries require a path string.")
    _validate_relative_evidence_path(path)
    description = item.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("evidence.artifacts entries require a description string.")
    return {
        "kind": kind,
        "path": path,
        "description": description,
    }


def _validate_evidence_command(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("evidence.verification_commands entries must be JSON objects.")
    command = item.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("evidence.verification_commands entries require a command string.")
    status = item.get("status")
    if status not in ALLOWED_TEST_STATUSES:
        raise ValueError(
            "evidence.verification_commands entries require status to be one of "
            f"{sorted(ALLOWED_TEST_STATUSES)}."
        )
    return {
        "command": command,
        "status": status,
    }


def _validate_relative_evidence_path(path: str) -> None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("evidence artifact paths must be repo-relative and must not contain '..'.")


def build_runner_package(step: dict[str, Any], *, runner: str = "generic", run_dir: str | None = None) -> dict[str, Any]:
    """Build the external runner contract from a harness step."""

    if runner not in ALLOWED_RUNNERS:
        raise ValueError(f"Unknown runner: {runner}. Expected one of {sorted(ALLOWED_RUNNERS)}.")

    prompt = step.get("prompt")
    should_execute = step.get("next_action") == "continue_executor" and isinstance(prompt, str) and bool(prompt.strip())
    context_pack = step.get("state", {}).get("context_pack") if isinstance(step.get("state"), dict) else None
    mode = step.get("state", {}).get("mode") if isinstance(step.get("state"), dict) else None
    run_id = str(step.get("run_id"))
    run_dir_flags = ["--run-dir", run_dir] if run_dir else []
    package: dict[str, Any] = {
        "schema": RUNNER_PACKAGE_SCHEMA,
        "runner": runner,
        "run_id": run_id,
        "next_action": step.get("next_action"),
        "should_execute": should_execute,
        "session_preflight": step.get("session_preflight"),
        "step": step,
        "execution": {
            "argv": _runner_argv(runner),
            "stdin": prompt if should_execute else None,
            "env": _runner_env(
                runner=runner,
                run_id=run_id,
                next_action=str(step.get("next_action")),
                context_pack=context_pack,
            ),
        },
        "report_back": {
            "argv": [
                "aspec",
                "run",
                "result",
                run_id,
                "--runner",
                runner,
                *run_dir_flags,
                "--result-json",
                "<runner-result-json>",
                "--json",
            ],
            "result_schema": RUNNER_RESULT_SCHEMA,
            "result_template": {
                "schema": RUNNER_RESULT_SCHEMA,
                "executor_output": "<executor-output>",
                "touched_paths": [],
                "test_status": "<not_run|passed|failed>",
                "evidence": runner_evidence_template(),
            },
            "legacy_step_argv": [
                "aspec",
                "run",
                "step",
                "--run-id",
                run_id,
                *run_dir_flags,
                "--executor-output",
                "<executor-output>",
                "--test-status",
                "<not_run|passed|failed>",
                "--json",
            ],
            "touched_path_flag": "--touched-path",
        },
    }
    if mode == "research":
        package["report_back"]["result_template"]["acceptance_evidence"] = research_acceptance_evidence_template()
    return package


def _run_dir_arg(root: Path, run_dir: Path | None) -> str | None:
    if run_dir is None:
        return None
    path = Path(run_dir)
    if not path.is_absolute():
        path = Path(root).resolve() / path
    return str(path.resolve())


def _runner_argv(runner: str) -> list[str]:
    if runner == "codex":
        return ["codex"]
    if runner == "claude":
        return ["claude"]
    return []


def _runner_env(*, runner: str, run_id: str, next_action: str, context_pack: Any) -> dict[str, str]:
    env = {
        "AGENTSPEC_RUN_ID": run_id,
        "AGENTSPEC_RUNNER": runner,
        "AGENTSPEC_NEXT_ACTION": next_action,
    }
    if isinstance(context_pack, str) and context_pack.strip():
        env["AGENTSPEC_CONTEXT_PACK"] = context_pack
    return env


def _default_demo_touched_paths(package: dict[str, Any]) -> list[str]:
    step = package.get("step")
    if not isinstance(step, dict):
        return []
    state = step.get("state")
    if not isinstance(state, dict):
        return []
    context_pack = state.get("context_pack")
    return [context_pack] if isinstance(context_pack, str) and context_pack else []


def _run_package_subprocess(
    root: Path,
    package: dict[str, Any],
    *,
    command: list[str] | None,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    argv = command if command is not None else list(package.get("execution", {}).get("argv") or [])
    if not argv:
        raise ValueError("Runner package has no command. Pass --command or --command-json, or use runner=codex|claude.")

    execution = package.get("execution", {})
    stdin = execution.get("stdin")
    env = os.environ.copy()
    package_env = execution.get("env")
    if isinstance(package_env, dict):
        env.update({str(key): str(value) for key, value in package_env.items()})

    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            input=stdin if isinstance(stdin, str) else None,
            text=True,
            capture_output=True,
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
        result = {
            "argv": argv,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
            "error": None,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "argv": argv,
            "returncode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "timed_out": True,
            "error": f"Runner command timed out after {timeout_seconds} seconds.",
        }
    except OSError as exc:
        result = {
            "argv": argv,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": f"Runner command failed to start: {exc}",
        }

    result["touched_paths"] = _git_changed_paths(root)
    return result


def _executor_output_from_subprocess(execution: dict[str, Any]) -> str:
    parts = [f"Runner command exited with returncode={execution.get('returncode')}."]
    if execution.get("timed_out"):
        parts.append("Runner command timed out.")
    error = execution.get("error")
    if isinstance(error, str) and error:
        parts.append(error)
    stdout = execution.get("stdout")
    if isinstance(stdout, str) and stdout.strip():
        parts.extend(["stdout:", stdout.strip()])
    stderr = execution.get("stderr")
    if isinstance(stderr, str) and stderr.strip():
        parts.extend(["stderr:", stderr.strip()])
    return "\n".join(parts)


def _git_changed_paths(root: Path) -> list[str]:
    available, paths = _git_changed_paths_with_status(root)
    return paths if available else []


def _git_changed_paths_with_status(root: Path) -> tuple[bool, list[str]]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False, []
    if completed.returncode != 0:
        return False, []

    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        path = path.strip().strip('"')
        if path:
            paths.append(path)
    return True, sorted(set(paths))


def _redact_execution(execution: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(execution)
    argv = redacted.get("argv")
    if isinstance(argv, list):
        redacted["argv"] = [
            redact_sensitive_text(item) if isinstance(item, str) else item
            for item in argv
        ]
    for key in ("stdout", "stderr", "error"):
        value = redacted.get(key)
        if isinstance(value, str):
            redacted[key] = redact_sensitive_text(value)
    return redacted


def _redact_runner_result(result: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(result)
    value = redacted.get("executor_output")
    if isinstance(value, str):
        redacted["executor_output"] = redact_sensitive_text(value)
    return redacted
