from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .run import step_run


RUNNER_PACKAGE_SCHEMA = "agentspec.runner_package.v0"
RUNNER_RESULT_SCHEMA = "agentspec.runner_result.v0"
RUNNER_DEMO_SCHEMA = "agentspec.runner_demo.v0"
RUNNER_EXEC_SCHEMA = "agentspec.runner_exec.v0"
ALLOWED_RUNNERS = {"generic", "codex", "claude"}
ALLOWED_TEST_STATUSES = {"not_run", "passed", "failed"}
ALLOWED_REVIEWER_MODES = {"deterministic", "model", "auto"}


def package_run(
    root: Path,
    context_pack: Path | None = None,
    *,
    runner: str = "generic",
    run_id: str | None = None,
    executor_output: str | None = None,
    touched_paths: list[str] | None = None,
    test_status: str = "not_run",
    reviewer_mode: str | None = None,
    task_type: str | None = None,
    order: str = "newest",
    max_iterations: int | None = None,
) -> dict[str, Any]:
    if runner not in ALLOWED_RUNNERS:
        raise ValueError(f"Unknown runner: {runner}. Expected one of {sorted(ALLOWED_RUNNERS)}.")

    step = step_run(
        root,
        context_pack,
        run_id=run_id,
        executor_output=executor_output,
        touched_paths=touched_paths or [],
        test_status=test_status,
        reviewer_mode=reviewer_mode,
        task_type=task_type,
        order=order,
        max_iterations=max_iterations,
    )
    return build_runner_package(step, runner=runner)


def submit_runner_result(
    root: Path,
    run_id: str,
    result: dict[str, Any],
    *,
    runner: str = "generic",
    reviewer_mode: str | None = None,
) -> dict[str, Any]:
    parsed = parse_runner_result(result)
    mode = reviewer_mode or parsed.get("reviewer_mode")
    return package_run(
        root,
        runner=runner,
        run_id=run_id,
        executor_output=str(parsed["executor_output"]),
        touched_paths=list(parsed["touched_paths"]),
        test_status=str(parsed["test_status"]),
        reviewer_mode=mode if isinstance(mode, str) else None,
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
) -> dict[str, Any]:
    initial_package = package_run(
        root,
        context_pack,
        runner=runner,
        run_id=run_id,
        task_type=task_type,
        order=order,
        max_iterations=max_iterations,
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
        transcript.append({"kind": "runner_result", "result": result})
        final_package = submit_runner_result(
            root,
            actual_run_id,
            result,
            runner=runner,
            reviewer_mode=reviewer_mode,
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
) -> dict[str, Any]:
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
    )
    actual_run_id = str(initial_package["run_id"])
    transcript: list[dict[str, Any]] = [{"kind": "package", "package": initial_package}]
    final_package = initial_package

    if initial_package.get("should_execute"):
        execution = _run_package_subprocess(
            root,
            initial_package,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        transcript.append({"kind": "subprocess", "execution": execution})
        result = {
            "schema": RUNNER_RESULT_SCHEMA,
            "executor_output": _executor_output_from_subprocess(execution),
            "touched_paths": touched_paths if touched_paths is not None else execution.get("touched_paths", []),
            "test_status": "failed" if execution.get("returncode") not in {0, None} or execution.get("error") else test_status,
        }
        if reviewer_mode is not None:
            result["reviewer_mode"] = reviewer_mode
        transcript.append({"kind": "runner_result", "result": result})
        final_package = submit_runner_result(
            root,
            actual_run_id,
            result,
            runner=runner,
            reviewer_mode=reviewer_mode,
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


def parse_runner_result(result: dict[str, Any]) -> dict[str, Any]:
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

    return {
        "schema": schema or RUNNER_RESULT_SCHEMA,
        "executor_output": executor_output,
        "touched_paths": touched_paths,
        "test_status": test_status,
        "reviewer_mode": reviewer_mode,
    }


def build_runner_package(step: dict[str, Any], *, runner: str = "generic") -> dict[str, Any]:
    if runner not in ALLOWED_RUNNERS:
        raise ValueError(f"Unknown runner: {runner}. Expected one of {sorted(ALLOWED_RUNNERS)}.")

    prompt = step.get("prompt")
    should_execute = step.get("next_action") == "continue_executor" and isinstance(prompt, str) and bool(prompt.strip())
    context_pack = step.get("state", {}).get("context_pack") if isinstance(step.get("state"), dict) else None
    run_id = str(step.get("run_id"))
    package = {
        "schema": RUNNER_PACKAGE_SCHEMA,
        "runner": runner,
        "run_id": run_id,
        "next_action": step.get("next_action"),
        "should_execute": should_execute,
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
            },
            "legacy_step_argv": [
                "aspec",
                "run",
                "step",
                "--run-id",
                run_id,
                "--executor-output",
                "<executor-output>",
                "--test-status",
                "<not_run|passed|failed>",
                "--json",
            ],
            "touched_path_flag": "--touched-path",
        },
    }
    return package


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
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if completed.returncode != 0:
        return []

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
    return sorted(set(paths))
