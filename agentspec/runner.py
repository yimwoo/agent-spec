from __future__ import annotations

from pathlib import Path
from typing import Any

from .run import step_run


RUNNER_PACKAGE_SCHEMA = "agentspec.runner_package.v0"
RUNNER_RESULT_SCHEMA = "agentspec.runner_result.v0"
RUNNER_DEMO_SCHEMA = "agentspec.runner_demo.v0"
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
