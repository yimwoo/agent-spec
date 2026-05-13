from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

from .compile import compile_project
from .dcr import (
    ALLOWED_CLASSIFICATIONS,
    accept_dcr,
    create_dcr_stub,
    list_dcrs,
    set_classification,
)
from .diagnostics import configure_diagnostics, get_logger
from .doctor import run_doctor
from .drift import run_drift
from .emit import emit_targets
from .errors import (
    AgentSpecError,
    AgentSpecIOPermissionError,
    AgentSpecValidationError,
    RunStateNotFoundError,
    RunnerResultInvalidError,
)
from .guidance import (
    build_artifact_preservation_guidance,
    build_post_artifact_guidance,
    format_artifact_preservation_guidance,
    format_post_artifact_guidance,
)
from .ingest import ingest_source
from .intake import diff_candidate, format_diff_report, import_candidate, promote_candidate
from .lifecycle import build_lifecycle_contract, format_lifecycle_contract
from .metrics import build_project_metrics, format_project_metrics
from .init import init_project
from .io import load_data
from .migration import format_legacy_execution_migration, migrate_legacy_execution
from .maturity import (
    ALLOWED_MATURITY_ENFORCEMENT,
    ALLOWED_MATURITY_LEVELS,
    build_maturity_status,
    format_maturity_status,
    set_maturity_config,
)
from .outcome import build_outcome_status, format_outcome_status
from .quality import run_quality_gc
from .requirement import accept_requirement
from .review import (
    ALLOWED_CODE_REVIEW_VERDICTS,
    ALLOWED_DOC_REVIEW_MODES,
    ALLOWED_DOC_REVIEW_REVIEWERS,
    ALLOWED_DOC_REVIEW_VERDICTS,
    check_doc_review,
    record_code_review,
    record_doc_review,
)
from .roadmap import check_roadmap, write_roadmap
from .run import abort_run, build_next_executor_prompt, complete_context_pack_run, inspect_run, loop_run, resume_run, start_run, step_run
from .runner import ALLOWED_RUNNERS, execute_runner, package_run, run_demo, submit_runner_result
from .session import (
    ALLOWED_FINISH_DISPOSITIONS,
    ALLOWED_SESSION_MODES,
    ALLOWED_TEST_STATUSES,
    build_session_preflight,
    finish_session,
    format_session_list,
    format_session_record,
    inspect_session,
    list_sessions,
    release_session,
    start_session,
)
from .source_registry import (
    add_source_record,
    check_registered_sources,
    format_source_check,
    format_source_list,
    list_source_records,
    source_check_exit_code,
)
from .spec_document import ALLOWED_CLASSIFICATIONS as SOURCE_CLASSIFICATIONS
from .spec_document import ALLOWED_KINDS, ALLOWED_STORAGE_MODES
from .status import agent_display_for_next_action, build_project_status, format_project_status
from .task import create_task_context_pack, create_task_context_pack_from_workflow, list_task_context_packs, next_task_context_pack
from .writeback import finish_task
from .workflow import build_workflow_contract_status, create_or_link_native_workflow, workflow_warning_lines


def _default_prog() -> str:
    invoked = Path(sys.argv[0]).name
    if invoked in {"agentspec", "aspec"}:
        return invoked
    return "agentspec"


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or _default_prog(),
        description="Compile design sources into agent-ready repository artifacts.",
    )
    parser.add_argument("--root", default=".", help="Project root. Defaults to the current directory.")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="Create AgentSpec artifact layout.")
    init.add_argument("--mode", default="greenfield", choices=["greenfield", "brownfield", "dogfood"])
    init.add_argument("--targets", default="claude,codex")
    init.add_argument("--archetype", default="code-agent-tooling")
    init.add_argument("--maturity", default="lightweight", choices=sorted(ALLOWED_MATURITY_LEVELS))
    init.add_argument("--maturity-enforcement", default="warn", choices=sorted(ALLOWED_MATURITY_ENFORCEMENT))

    ingest = subparsers.add_parser("ingest", help="Import and sectionize a Markdown source document.")
    ingest.add_argument("path")
    ingest.add_argument("--classification", default="internal", choices=["public", "internal", "confidential", "restricted"])
    ingest.add_argument("--storage-mode", default="committed", choices=["committed", "local-secure-cache", "enterprise-object-store", "pointer-only"])

    intake = subparsers.add_parser("intake", help="Import external sources as candidate snapshots.")
    intake_subparsers = intake.add_subparsers(dest="intake_command")
    intake_import = intake_subparsers.add_parser("import", help="Import a source as a candidate snapshot.")
    intake_import.add_argument("path")
    intake_import.add_argument("--kind", required=True, choices=sorted(ALLOWED_KINDS))
    intake_import.add_argument("--source-key", required=True)
    intake_import.add_argument("--classification", required=True, choices=sorted(SOURCE_CLASSIFICATIONS))
    intake_import.add_argument("--storage-mode", required=True, choices=sorted(ALLOWED_STORAGE_MODES))
    intake_import.add_argument("--as-candidate", action="store_true")
    intake_import.add_argument("--json", action="store_true")
    intake_diff = intake_subparsers.add_parser("diff", help="Diff a candidate snapshot against a baseline.")
    intake_diff.add_argument("snapshot_id")
    intake_diff.add_argument("--baseline", default="accepted", choices=["accepted"])
    intake_diff.add_argument("--json", action="store_true")
    intake_promote = intake_subparsers.add_parser("promote", help="Promote a candidate snapshot into accepted source projection.")
    intake_promote.add_argument("snapshot_id")
    intake_promote.add_argument("--decision", required=True, choices=["accepted"])
    intake_promote.add_argument("--compile", action="store_true")
    intake_promote.add_argument("--json", action="store_true")

    source = subparsers.add_parser("source", help="Registered external source utilities.")
    source_subparsers = source.add_subparsers(dest="source_command")
    source_add = source_subparsers.add_parser("add", help="Add or update a registered external source.")
    source_add.add_argument("source_key")
    source_add.add_argument("remote_uri")
    source_add.add_argument("--kind", required=True, choices=sorted(ALLOWED_KINDS))
    source_add.add_argument("--classification", required=True, choices=sorted(SOURCE_CLASSIFICATIONS))
    source_add.add_argument("--storage-mode", required=True, choices=sorted(ALLOWED_STORAGE_MODES))
    source_add.add_argument("--poll-cadence")
    source_add.add_argument("--json", action="store_true")
    source_list = source_subparsers.add_parser("list", help="List registered external sources.")
    source_list.add_argument("--json", action="store_true")
    source_check = source_subparsers.add_parser("check", help="Check registered sources for source drift.")
    source_check.add_argument("source_key", nargs="?")
    source_check.add_argument("--all", action="store_true", dest="all_sources")
    source_check.add_argument("--as-candidate", action="store_true")
    source_check.add_argument("--json", action="store_true")

    subparsers.add_parser("compile", help="Compile source sections into specs, requirements, assumptions, questions, and readiness.")

    readiness = subparsers.add_parser("readiness", help="Print readiness score.")
    readiness.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Print project progress status.")
    status.add_argument("--json", action="store_true")
    status.add_argument("--recent-runs", type=int, default=5)

    lifecycle = subparsers.add_parser(
        "lifecycle",
        help="Print the native AgentSpec lifecycle operating contract.",
    )
    lifecycle.add_argument("--json", action="store_true")

    guidance = subparsers.add_parser("guidance", help="Project post-artifact next-step guidance.")
    guidance.add_argument("artifact", help="Artifact path to inspect.")
    guidance.add_argument("--json", action="store_true")

    quality = subparsers.add_parser("quality", help="Run recurring quality garbage-collection diagnostics.")
    quality.add_argument("--json", action="store_true")
    quality.add_argument("--report-dir", help="Write reports under <path>/quality/ instead of <root>/reports/quality/.")
    quality.add_argument("--task-interval", type=int, default=3, help="Completed-task interval for quality GC cadence hints.")

    metrics = subparsers.add_parser("metrics", help="Print read-only project feedback-loop metrics.")
    metrics.add_argument("--json", action="store_true")

    roadmap = subparsers.add_parser("roadmap", help="Generate or check docs/ROADMAP.md.")
    roadmap.add_argument("--check", action="store_true", help="Fail if docs/ROADMAP.md is missing or stale.")
    roadmap.add_argument("--json", action="store_true")

    plan = subparsers.add_parser(
        "plan",
        help="Create or link an AgentSpec workflow for a task context pack.",
        description="Create or link an AgentSpec workflow for a task context pack.",
    )
    plan.add_argument("selector", nargs="?", help="Task id (for example T-092) or context pack path.")
    plan.add_argument("--from-task", dest="from_task", help="Task id or context pack path to plan from.")
    plan.add_argument("--current", action="store_true", help="Use the current next ready task context pack.")
    plan.add_argument("--json", action="store_true")

    finish = subparsers.add_parser(
        "finish",
        help="Finish a task by orchestrating completion write-back.",
        description="Finish a task by orchestrating completion write-back.",
    )
    finish.add_argument("selector", nargs="?", help="Task id (for example T-094) or context pack path.")
    finish.add_argument("--current", action="store_true", help="Use the active or next current task context pack.")
    finish.add_argument("--dry-run", action="store_true", help="Report finish readiness without mutating state.")
    finish.add_argument("--run-id")
    finish.add_argument("--reason", default="Finished by user.")
    finish.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    finish.add_argument("--review", dest="review_id", help="Code review id to link before completion.")
    finish.add_argument("--json", action="store_true")

    migrate = subparsers.add_parser("migrate", help="Migration utilities.")
    migrate_subparsers = migrate.add_subparsers(dest="migrate_command")
    migrate_legacy = migrate_subparsers.add_parser(
        "legacy-execution",
        help="Migrate legacy execution artifacts into AgentSpec governance.",
        description="Migrate legacy execution artifacts into AgentSpec governance.",
    )
    migrate_legacy.add_argument("--from", dest="from_path", help="Limit migration to one scanner-recognized legacy execution artifact.")
    migrate_legacy.add_argument("--write", action="store_true", help="Create missing AgentSpec task context packs. Defaults to dry-run.")
    migrate_legacy.add_argument("--json", action="store_true")

    outcome = subparsers.add_parser("outcome", help="Print product outcome readiness gates.")
    outcome.add_argument("--json", action="store_true")

    maturity = subparsers.add_parser("maturity", help="Print or update progressive maturity profile status.")
    maturity_subparsers = maturity.add_subparsers(dest="maturity_command")
    maturity_status = maturity_subparsers.add_parser("status", help="Print maturity profile status.")
    maturity_status.add_argument("--json", action="store_true")
    maturity_check = maturity_subparsers.add_parser("check", help="Check maturity profile readiness.")
    maturity_check.add_argument("--json", action="store_true")
    maturity_set = maturity_subparsers.add_parser("set", help="Set the maturity profile level.")
    maturity_set.add_argument("level", choices=sorted(ALLOWED_MATURITY_LEVELS))
    maturity_set.add_argument("--enforcement", default="warn", choices=sorted(ALLOWED_MATURITY_ENFORCEMENT))
    maturity_set.add_argument("--json", action="store_true")

    session = subparsers.add_parser("session", help="Multi-session worktree lease utilities.")
    session_subparsers = session.add_subparsers(dest="session_command")
    session_start = session_subparsers.add_parser("start", help="Create an active AgentSpec session lease.")
    session_start.add_argument("--task", required=True, help="Task id (for example T-086) or context pack path.")
    session_start.add_argument("--owner", help="Human, agent, or tool claiming the lease.")
    session_start.add_argument("--mode", default="owner", choices=sorted(ALLOWED_SESSION_MODES))
    session_start.add_argument("--branch", help="Associated git branch, if any.")
    session_start.add_argument("--worktree", help="Associated git worktree path, if any.")
    session_start.add_argument(
        "--allow-shared",
        action="store_true",
        help="Allow an owner/patcher session to share an active branch or worktree lease.",
    )
    session_start.add_argument("--session-id", help="Override the generated session id.")
    session_start.add_argument("--run-id", help="Associated AgentSpec run id, if any.")
    session_start.add_argument("--note", help="Optional session note.")
    session_start.add_argument("--json", action="store_true")
    session_list = session_subparsers.add_parser("list", help="List active and archived session leases.")
    session_list.add_argument("--json", action="store_true")
    session_inspect = session_subparsers.add_parser("inspect", help="Inspect one active or archived session lease.")
    session_inspect.add_argument("session_id")
    session_inspect.add_argument("--json", action="store_true")
    session_finish = session_subparsers.add_parser("finish", help="Archive an active session lease with a disposition.")
    session_finish.add_argument("session_id")
    session_finish.add_argument("--disposition", required=True, choices=sorted(ALLOWED_FINISH_DISPOSITIONS))
    session_finish.add_argument("--review", dest="review_id", help="Linked review id, if completion had review evidence.")
    session_finish.add_argument("--test-status", default="not_run", choices=sorted(ALLOWED_TEST_STATUSES))
    session_finish.add_argument("--note", help="Optional finish note.")
    session_finish.add_argument("--json", action="store_true")
    session_release = session_subparsers.add_parser("release", help="Archive an active session lease without completion.")
    session_release.add_argument("session_id")
    session_release.add_argument("--reason", help="Optional release reason.")
    session_release.add_argument("--json", action="store_true")

    subparsers.add_parser(
        "next-action",
        help="Dispatch the next recovery or continuation action from project status.",
    )
    subparsers.add_parser("continue", help="Alias for next-action.")

    doctor = subparsers.add_parser("doctor", help="Run read-only brownfield assessment.")
    doctor.add_argument(
        "--report-dir",
        help="Write reports under <path>/doctor/ instead of <root>/reports/doctor/. Use for read-only target checkouts.",
    )

    repo = subparsers.add_parser("repo", help="Repository utilities.")
    repo_subparsers = repo.add_subparsers(dest="repo_command")
    repo_scan = repo_subparsers.add_parser("scan", help="Alias for doctor.")
    repo_scan.add_argument(
        "--report-dir",
        help="Write reports under <path>/doctor/ instead of <root>/reports/doctor/. Use for read-only target checkouts.",
    )

    review = subparsers.add_parser("review", help="Review evidence utilities.")
    review_subparsers = review.add_subparsers(dest="review_command")
    review_code = review_subparsers.add_parser("code", help="Record task-level code review evidence.")
    review_code.add_argument("--task", required=True, help="Task id or context pack path.")
    review_code.add_argument("--verdict", required=True, choices=sorted(ALLOWED_CODE_REVIEW_VERDICTS))
    review_code.add_argument("--summary", required=True)
    review_code.add_argument("--reviewer", default="human")
    review_code.add_argument("--range", dest="range_ref", default="worktree")
    review_code.add_argument("--json", action="store_true")
    review_doc = review_subparsers.add_parser("doc", help="Record or check document review evidence.")
    review_doc.add_argument("artifact", nargs="?", help="Document artifact path to review.")
    review_doc.add_argument("--mode", choices=sorted(ALLOWED_DOC_REVIEW_MODES))
    review_doc.add_argument("--verdict", choices=sorted(ALLOWED_DOC_REVIEW_VERDICTS))
    review_doc.add_argument("--reviewer", choices=sorted(ALLOWED_DOC_REVIEW_REVIEWERS))
    review_doc.add_argument("--summary")
    review_doc.add_argument("--check", dest="check_artifact", help="Check review freshness for a document without writing evidence.")
    review_doc.add_argument("--json", action="store_true")

    task = subparsers.add_parser("task", help="Task utilities.")
    task_subparsers = task.add_subparsers(dest="task_command")
    task_create = task_subparsers.add_parser("create", help="Create a task context pack.")
    task_create.add_argument("--requirement")
    task_create.add_argument("--from-workflow", dest="from_workflow", help="Backfill a context pack from a workflow or state file.")
    task_create.add_argument("--type", default="implementation", choices=["discovery", "spec", "spike", "scaffold", "implementation", "review", "migration", "automation"])
    task_create.add_argument("--title")
    task_list = task_subparsers.add_parser("list", help="List task context packs.")
    task_list.add_argument("--type")
    task_list.add_argument("--status")
    task_list.add_argument("--json", action="store_true")
    task_next = task_subparsers.add_parser("next", help="Print the next ready task context pack.")
    task_next.add_argument("--type")
    task_next.add_argument("--order", default="newest", choices=["oldest", "newest"])
    task_next.add_argument("--json", action="store_true")
    task_complete = task_subparsers.add_parser("complete", help="Mark a context pack complete by writing run state.")
    task_complete.add_argument("selector", help="Task id (e.g. T-013) or context pack path.")
    task_complete.add_argument("--run-id")
    task_complete.add_argument("--reason", default="Marked complete by user.")
    task_complete.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    task_complete.add_argument("--review", dest="review_id", help="Code review id to link before completion.")
    task_complete.add_argument("--json", action="store_true")

    context = subparsers.add_parser("context", help="Context pack utilities.")
    context_subparsers = context.add_subparsers(dest="context_command")
    context_build = context_subparsers.add_parser("build", help="Create a task context pack.")
    context_build.add_argument("--requirement")
    context_build.add_argument("--from-workflow", dest="from_workflow")
    context_build.add_argument("--type", default="implementation")
    context_build.add_argument("--title")

    emit = subparsers.add_parser("emit", help="Generate agent integration artifacts.")
    emit.add_argument("--target", default="agents-md", help="Comma-separated targets: agents-md,claude,codex,github-actions,all")

    drift = subparsers.add_parser("drift", help="Generate a spec drift review report.")
    drift.add_argument("--diff")
    drift.add_argument(
        "--report-dir",
        help="Write the drift report under <path>/drift/ instead of <root>/reports/drift/. Use for read-only target checkouts.",
    )

    run = subparsers.add_parser("run", help="Supervised run utilities.")
    run_subparsers = run.add_subparsers(dest="run_command")
    run_start = run_subparsers.add_parser("start", help="Create local supervised-run state for a context pack.")
    run_start.add_argument("context_pack")
    run_start.add_argument("--run-id")
    run_start.add_argument("--run-dir", help="Store run state under <path>/<run-id>/ instead of <root>/agent/runs/<run-id>/.")
    run_start.add_argument("--max-iterations", type=int)
    run_start.add_argument("--mode", default="supervised", choices=["supervised", "autonomous"])

    run_resume = run_subparsers.add_parser("resume", help="Record an executor iteration and reviewer verdict.")
    run_resume.add_argument("run_id")
    run_resume.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_resume.add_argument("--executor-output", required=True)
    run_resume.add_argument("--touched-path", action="append", default=[])
    run_resume.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_resume.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])

    run_loop = run_subparsers.add_parser("loop", help="Select, start, or resume the next supervised run step.")
    run_loop.add_argument("context_pack", nargs="?")
    run_loop.add_argument("--run-id")
    run_loop.add_argument("--run-dir", help="Store run state under <path>/<run-id>/ instead of <root>/agent/runs/<run-id>/.")
    run_loop.add_argument("--executor-output")
    run_loop.add_argument("--touched-path", action="append", default=[])
    run_loop.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_loop.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_loop.add_argument("--type", dest="task_type")
    run_loop.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_loop.add_argument("--max-iterations", type=int)
    run_loop.add_argument("--mode", default="supervised", choices=["supervised", "autonomous"])
    run_loop.add_argument("--json", action="store_true")

    run_step = run_subparsers.add_parser("step", help="Run one harness control-plane step.")
    run_step.add_argument("context_pack", nargs="?")
    run_step.add_argument("--run-id")
    run_step.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_step.add_argument("--executor-output")
    run_step.add_argument("--touched-path", action="append", default=[])
    run_step.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_step.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_step.add_argument("--type", dest="task_type")
    run_step.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_step.add_argument("--max-iterations", type=int)
    run_step.add_argument("--json", action="store_true")

    run_package = run_subparsers.add_parser("package", help="Prepare a runner execution package for one harness step.")
    run_package.add_argument("context_pack", nargs="?")
    run_package.add_argument("--runner", default="generic", choices=sorted(ALLOWED_RUNNERS))
    run_package.add_argument("--run-id")
    run_package.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_package.add_argument("--executor-output")
    run_package.add_argument("--touched-path", action="append", default=[])
    run_package.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_package.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_package.add_argument("--type", dest="task_type")
    run_package.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_package.add_argument("--max-iterations", type=int)
    run_package.add_argument("--json", action="store_true")

    run_result = run_subparsers.add_parser("result", help="Submit a structured runner result and return the next package.")
    run_result.add_argument("run_id")
    run_result.add_argument("--runner", default="generic", choices=sorted(ALLOWED_RUNNERS))
    run_result.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_result.add_argument("--result-json", required=True, help="Runner result JSON, or '-' to read stdin.")
    run_result.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_result.add_argument("--json", action="store_true")

    run_demo_parser = run_subparsers.add_parser("demo", help="Run a deterministic local package/result demo.")
    run_demo_parser.add_argument("context_pack", nargs="?")
    run_demo_parser.add_argument("--runner", default="generic", choices=sorted(ALLOWED_RUNNERS))
    run_demo_parser.add_argument("--run-id")
    run_demo_parser.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_demo_parser.add_argument("--executor-output", default="Done. Acceptance criteria are met.")
    run_demo_parser.add_argument("--touched-path", action="append", default=[])
    run_demo_parser.add_argument("--test-status", default="passed", choices=["not_run", "passed", "failed"])
    run_demo_parser.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_demo_parser.add_argument("--type", dest="task_type")
    run_demo_parser.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_demo_parser.add_argument("--max-iterations", type=int)
    run_demo_parser.add_argument("--json", action="store_true")

    run_exec = run_subparsers.add_parser("exec", help="Execute one runner package with a local subprocess.")
    run_exec.add_argument("context_pack", nargs="?")
    run_exec.add_argument("--runner", default="generic", choices=sorted(ALLOWED_RUNNERS))
    run_exec.add_argument("--run-id")
    run_exec.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_exec.add_argument("--command", dest="runner_command", help="Shell-like command string to split and execute without a shell.")
    run_exec.add_argument("--command-json", help="JSON array command argv to execute.")
    run_exec.add_argument("--touched-path", action="append", default=[])
    run_exec.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_exec.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_exec.add_argument("--type", dest="task_type")
    run_exec.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_exec.add_argument("--max-iterations", type=int)
    run_exec.add_argument("--timeout", type=float)
    run_exec.add_argument("--json", action="store_true")

    run_inspect = run_subparsers.add_parser("inspect", help="Print current supervised-run state.")
    run_inspect.add_argument("run_id")
    run_inspect.add_argument("--run-dir", help="Read run state under <path>/<run-id>/.")

    run_prompt = run_subparsers.add_parser("prompt", help="Print the next executor handoff prompt.")
    run_prompt.add_argument("run_id")
    run_prompt.add_argument("--run-dir", help="Read run state under <path>/<run-id>/.")
    run_prompt.add_argument("--json", action="store_true")

    run_abort = run_subparsers.add_parser("abort", help="Abort a supervised run.")
    run_abort.add_argument("run_id")
    run_abort.add_argument("--run-dir", help="Read and write run state under <path>/<run-id>/.")
    run_abort.add_argument("--reason", default="Aborted by user.")

    dcr = subparsers.add_parser("dcr", help="Design Change Request utilities.")
    dcr_subparsers = dcr.add_subparsers(dest="dcr_command")

    dcr_create = dcr_subparsers.add_parser("create", help="Create a new DCR document.")
    dcr_create.add_argument("--title", required=True)
    dcr_create.add_argument("--classification", required=True, choices=sorted(ALLOWED_CLASSIFICATIONS))
    dcr_create.add_argument("--id", dest="dcr_id_override", help="Override the auto-numbered DCR id (e.g. DCR-0099).")
    dcr_create.add_argument("--json", action="store_true")

    dcr_classify = dcr_subparsers.add_parser("classify", help="Update an existing DCR's classification.")
    dcr_classify.add_argument("dcr_id")
    dcr_classify.add_argument("--to", dest="classification", required=True, choices=sorted(ALLOWED_CLASSIFICATIONS))

    dcr_accept = dcr_subparsers.add_parser("accept", help="Flip a DCR to accepted without changing requirements.")
    dcr_accept.add_argument("dcr_id")

    dcr_subparsers.add_parser("list", help="List all DCRs in the workspace.")

    requirement = subparsers.add_parser("requirement", help="Requirement utilities.")
    requirement_subparsers = requirement.add_subparsers(dest="requirement_command")
    requirement_accept = requirement_subparsers.add_parser(
        "accept", help="Flip a single proposed-pending-acceptance requirement to accepted."
    )
    requirement_accept.add_argument("requirement_id")

    dogfood = subparsers.add_parser("dogfood", help="Dogfood / experiment notes.")
    dogfood_subparsers = dogfood.add_subparsers(dest="dogfood_command")
    dogfood_record = dogfood_subparsers.add_parser(
        "record", help="Write a dogfood-finding stub under reports/dogfood/."
    )
    dogfood_record.add_argument("--title", required=True)
    dogfood_record.add_argument("--slug", required=True)

    mcp = subparsers.add_parser("mcp", help="MCP utilities.")
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command")
    serve = mcp_subparsers.add_parser("serve", help="MVP placeholder for future MCP server.")
    serve.add_argument("--stdio", action="store_true")
    serve.add_argument("--http")

    return parser


def main(argv: list[str] | None = None, prog: str | None = None) -> int:
    parser = build_parser(prog=prog)
    args = parser.parse_args(argv)
    configure_diagnostics(os.environ)
    root = Path(args.root).resolve()

    try:
        if args.command == "init":
            written = init_project(
                root,
                mode=args.mode,
                targets=args.targets,
                archetype=args.archetype,
                maturity=args.maturity,
                maturity_enforcement=args.maturity_enforcement,
            )
            print(f"Initialized AgentSpec workspace at {root} ({len(written)} files created).")
            return 0

        if args.command == "ingest":
            result = ingest_source(root, Path(args.path), classification=args.classification, storage_mode=args.storage_mode)
            print(f"Ingested {result['source']['uri']} as {result['source']['id']} with {len(result['sections'])} sections.")
            return 0

        if args.command == "intake":
            if args.intake_command == "import":
                if not args.as_candidate:
                    raise ValueError("intake import requires --as-candidate.")
                result = import_candidate(
                    root,
                    Path(args.path),
                    kind=args.kind,
                    source_key=args.source_key,
                    classification=args.classification,
                    storage_mode=args.storage_mode,
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(f"Imported {result['source_key']} as candidate {result['snapshot_id']}.")
                return 0
            if args.intake_command == "diff":
                result = diff_candidate(root, args.snapshot_id, baseline=args.baseline)
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(format_diff_report(result))
                return 0
            if args.intake_command == "promote":
                result = promote_candidate(
                    root,
                    args.snapshot_id,
                    decision=args.decision,
                    run_compile=args.compile,
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(
                        f"Promoted {result['snapshot_id']} as accepted source "
                        f"{result['accepted_source']['id']}."
                    )
                    if not result["compile"]["ran"]:
                        print(f"Next: {result['compile']['command']}")
                return 0
            parser.print_help()
            return 0

        if args.command == "source":
            if args.source_command == "add":
                result = add_source_record(
                    root,
                    source_key=args.source_key,
                    remote_uri=args.remote_uri,
                    kind=args.kind,
                    classification=args.classification,
                    storage_mode=args.storage_mode,
                    poll_cadence=args.poll_cadence,
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(
                        f"{result['action'].title()} source "
                        f"{result['record']['source_key']} -> {result['record']['remote_uri']}."
                    )
                return 0
            if args.source_command == "list":
                result = list_source_records(root)
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(format_source_list(result))
                return 0
            if args.source_command == "check":
                if args.all_sources and args.source_key:
                    raise ValueError("source check accepts either <source-key> or --all, not both.")
                if not args.all_sources and not args.source_key:
                    raise ValueError("source check requires <source-key> or --all.")
                result = check_registered_sources(
                    root,
                    source_key=args.source_key,
                    all_sources=args.all_sources,
                    as_candidate=args.as_candidate,
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(format_source_check(result))
                return source_check_exit_code(result)
            parser.print_help()
            return 0

        if args.command == "compile":
            result = compile_project(root)
            print(
                "Compiled "
                f"{len(result['spec_shards'])} spec shards, "
                f"{len(result['requirements'])} requirements, "
                f"{len(result['open_questions'])} open questions. "
                f"Readiness: {result['readiness']['score']}/100."
            )
            return 0

        if args.command == "readiness":
            readiness = load_data(root / "docs" / "discovery" / "readiness.yml", {"score": 0, "mode": "discovery", "summary": "Not compiled."})
            if args.json:
                print(json.dumps(readiness, indent=2))
            else:
                print(readiness.get("summary", f"Readiness is {readiness.get('score', 0)}/100."))
            return 0

        if args.command == "status":
            status_payload = build_project_status(root, recent_limit=args.recent_runs)
            if args.json:
                print(json.dumps(status_payload, indent=2))
            else:
                print(format_project_status(status_payload))
            return 0

        if args.command == "lifecycle":
            lifecycle_payload = build_lifecycle_contract(root)
            if args.json:
                print(json.dumps(lifecycle_payload, indent=2))
            else:
                print(format_lifecycle_contract(lifecycle_payload))
            return 0

        if args.command == "guidance":
            guidance_payload = build_post_artifact_guidance(root, args.artifact)
            if args.json:
                print(json.dumps(guidance_payload, indent=2))
            else:
                print(format_post_artifact_guidance(guidance_payload))
            return 0

        if args.command == "quality":
            report_dir = Path(args.report_dir) if args.report_dir else None
            report = run_quality_gc(root, report_dir=report_dir, task_interval=args.task_interval)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                markdown = report.get("reports", {}).get("markdown", "reports/quality/latest.md")
                print(f"Quality GC grade: {report['grade']} ({len(report['findings'])} finding(s)).")
                print(f"Report: {markdown}")
            return 0

        if args.command == "metrics":
            metrics_payload = build_project_metrics(root)
            if args.json:
                print(json.dumps(metrics_payload, indent=2))
            else:
                print(format_project_metrics(metrics_payload))
            return 0

        if args.command == "roadmap":
            if args.check:
                result = check_roadmap(root)
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(result["summary"])
                return 0 if result["current"] else 1
            path = write_roadmap(root)
            if args.json:
                print(json.dumps({"path": str(path.relative_to(root))}, indent=2))
            else:
                print(f"Wrote roadmap: {path.relative_to(root)}")
            return 0

        if args.command == "plan":
            selectors = [value for value in [args.selector, args.from_task] if value]
            if args.current:
                current = next_task_context_pack(root)
                if current is None:
                    raise ValueError("No ready task context pack found.")
                selectors.append(str(current["path"]))
            if len(selectors) != 1:
                raise ValueError("Select exactly one task with <task>, --from-task, or --current.")
            result = create_or_link_native_workflow(root, selectors[0])
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                action = "Created" if result.get("created") else "Linked"
                print(f"{action} workflow: {result['workflow_path']}")
                print(f"Task pack: {result['task_pack']}")
                print(f"Next: {result['next_command']}")
            return 0

        if args.command == "finish":
            result = finish_task(
                root,
                args.selector,
                current=args.current,
                dry_run=args.dry_run,
                run_id=args.run_id,
                reason=args.reason,
                test_status=args.test_status,
                review_id=args.review_id,
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                _print_finish_result(result)
            if result.get("dry_run") and result.get("enforcement") == "strict" and not result.get("finishable"):
                return 1
            return 0

        if args.command == "migrate":
            if args.migrate_command == "legacy-execution":
                result = migrate_legacy_execution(
                    root,
                    from_path=args.from_path,
                    write=args.write,
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(format_legacy_execution_migration(result))
                return 0
            parser.print_help()
            return 0

        if args.command == "outcome":
            outcome_payload = build_outcome_status(root)
            if args.json:
                print(json.dumps(outcome_payload, indent=2))
            else:
                print(format_outcome_status(outcome_payload))
            return 0

        if args.command == "maturity":
            if args.maturity_command in {"status", "check"}:
                maturity_payload = build_maturity_status(root)
                if args.json:
                    print(json.dumps(maturity_payload, indent=2))
                else:
                    print(format_maturity_status(maturity_payload))
                return 0
            if args.maturity_command == "set":
                maturity_payload = set_maturity_config(
                    root,
                    level=args.level,
                    enforcement=args.enforcement,
                )
                if args.json:
                    print(json.dumps(maturity_payload, indent=2))
                else:
                    print(format_maturity_status(maturity_payload))
                return 0
            parser.print_help()
            return 0

        if args.command == "session":
            if args.session_command == "start":
                record = start_session(
                    root,
                    task_selector=args.task,
                    owner=args.owner,
                    mode=args.mode,
                    branch=args.branch,
                    worktree=args.worktree,
                    allow_shared=args.allow_shared,
                    session_id=args.session_id,
                    run_id=args.run_id,
                    note=args.note,
                )
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(f"Started session {record['session_id']} for {record['context_pack']}.")
                return 0
            if args.session_command == "list":
                payload = list_sessions(root)
                if args.json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(format_session_list(payload))
                return 0
            if args.session_command == "inspect":
                record = inspect_session(root, args.session_id)
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(format_session_record(record))
                return 0
            if args.session_command == "finish":
                record = finish_session(
                    root,
                    args.session_id,
                    disposition=args.disposition,
                    review_id=args.review_id,
                    test_status=args.test_status,
                    note=args.note,
                )
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(
                        f"Finished session {record['session_id']} "
                        f"with disposition {record['disposition']}."
                    )
                return 0
            if args.session_command == "release":
                record = release_session(root, args.session_id, reason=args.reason)
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(f"Released session {record['session_id']}.")
                return 0
            parser.print_help()
            return 0

        if args.command in {"next-action", "continue"}:
            return _dispatch_next_action(root)

        if args.command == "doctor" or (args.command == "repo" and args.repo_command == "scan"):
            report_dir = Path(args.report_dir) if args.report_dir else None
            scan = run_doctor(root, report_dir=report_dir)
            destination = report_dir / "doctor" if report_dir else root / "reports" / "doctor"
            print(f"Doctor scan complete: {destination / 'repo-scan.yml'}")
            print(f"Languages: {', '.join(scan['repo']['languages']) or '-'}")
            return 0

        if args.command == "review":
            if args.review_command == "code":
                record = record_code_review(
                    root,
                    task_selector=args.task,
                    verdict=args.verdict,
                    summary=args.summary,
                    reviewer=args.reviewer,
                    range_ref=args.range_ref,
                )
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(f"Recorded code review {record['id']} ({record['verdict']}).")
                    _print_artifact_preservation(
                        build_artifact_preservation_guidance(
                            root,
                            [Path("agent") / "reviews" / f"{record['id']}.yml"],
                        )
                    )
                return 0
            if args.review_command == "doc":
                selected_doc_review_actions = sum(
                    value is not None for value in (args.check_artifact, args.mode, args.verdict)
                )
                if selected_doc_review_actions != 1:
                    raise ValueError("Document review requires exactly one of --mode, --verdict, or --check.")
                if args.check_artifact and args.artifact:
                    raise ValueError("Use --check <path> without a positional document artifact.")
                if args.check_artifact:
                    record = check_doc_review(root, artifact_selector=args.check_artifact)
                    if args.json:
                        print(json.dumps(record, indent=2))
                    else:
                        print(f"Document review {record['readiness']}: {record['artifact_path']}.")
                    return 0
                record = record_doc_review(
                    root,
                    artifact_selector=args.artifact,
                    mode=args.mode,
                    verdict=args.verdict,
                    reviewer=args.reviewer,
                    summary=args.summary,
                )
                if args.json:
                    print(json.dumps(record, indent=2))
                else:
                    print(f"Recorded document review {record['id']} ({record['verdict']}).")
                    _print_artifact_preservation(
                        build_artifact_preservation_guidance(
                            root,
                            [Path("agent") / "doc-reviews" / f"{record['id']}.yml"],
                        )
                    )
                return 0
            parser.print_help()
            return 0

        if args.command == "task" and args.task_command == "create":
            if args.from_workflow:
                path = create_task_context_pack_from_workflow(
                    root,
                    Path(args.from_workflow),
                    requirement_id=args.requirement,
                    task_type=args.type,
                    title=args.title,
                )
            else:
                path = create_task_context_pack(root, requirement_id=args.requirement, task_type=args.type, title=args.title)
            print(f"Created task context pack: {path.relative_to(root)}")
            _print_artifact_preservation(
                build_artifact_preservation_guidance(root, [path.relative_to(root)])
            )
            return 0

        if args.command == "task" and args.task_command == "list":
            records = list_task_context_packs(root, task_type=args.type, status=args.status)
            if args.json:
                print(json.dumps(records, indent=2))
            else:
                for record in records:
                    print(f"{record['id']}\t{record['status']}\t{record['type']}\t{record['path']}\t{record['title']}")
            return 0

        if args.command == "task" and args.task_command == "next":
            record = next_task_context_pack(root, task_type=args.type, order=args.order)
            if record is None:
                warnings = workflow_warning_lines(build_workflow_contract_status(root))
                status_payload = build_project_status(root, recent_limit=0)
                summary = status_payload.get("lifecycle_summary") if isinstance(status_payload, dict) else {}
                summary = summary if isinstance(summary, dict) else {}
                summary = _task_next_no_ready_summary(summary, args.type)
                action = summary.get("recommended_next_action") if isinstance(summary.get("recommended_next_action"), dict) else {}
                commands = action.get("commands") if isinstance(action.get("commands"), list) else []
                options = action.get("options") if isinstance(action.get("options"), list) else []
                agent_next_action = (
                    action.get("agent_display")
                    if isinstance(action.get("agent_display"), dict)
                    else agent_display_for_next_action(action)
                )
                if args.json:
                    print(
                        json.dumps(
                            {
                                "task": None,
                                "reason": summary.get("main_point", "No ready task context pack found."),
                                "next_commands": commands,
                                "next_options": options,
                                "agent_next_action": agent_next_action,
                                "lifecycle_summary": summary,
                                "workflow_warnings": warnings,
                            },
                            indent=2,
                        )
                    )
                else:
                    _print_no_ready_task(summary, warnings)
                    for warning in warnings:
                        print(f"Warning: {warning}")
                return 1
            if args.json:
                payload = dict(record)
                payload["session_preflight"] = build_session_preflight(
                    root,
                    context_pack=str(record.get("path") or ""),
                    task_id=str(record.get("id") or ""),
                    task_type=str(record.get("type") or "implementation"),
                )
                print(json.dumps(payload, indent=2))
            else:
                print(f"{record['path']}")
            return 0

        if args.command == "task" and args.task_command == "complete":
            state = complete_context_pack_run(
                root,
                args.selector,
                run_id=args.run_id,
                reason=args.reason,
                test_status=args.test_status,
                review_id=args.review_id,
                allow_existing_run=True,
            )
            if args.json:
                print(json.dumps(state, indent=2))
            else:
                print(f"Marked {state['context_pack']} complete via run {state['run_id']}.")
            return 0

        if args.command == "context" and args.context_command == "build":
            if args.from_workflow:
                path = create_task_context_pack_from_workflow(
                    root,
                    Path(args.from_workflow),
                    requirement_id=args.requirement,
                    task_type=args.type,
                    title=args.title,
                )
            else:
                path = create_task_context_pack(root, requirement_id=args.requirement, task_type=args.type, title=args.title)
            print(f"Created task context pack: {path.relative_to(root)}")
            return 0

        if args.command == "emit":
            written = emit_targets(root, args.target)
            print(f"Emitted {len(written)} integration artifacts.")
            return 0

        if args.command == "drift":
            report_dir = Path(args.report_dir) if args.report_dir else None
            path = run_drift(root, diff_ref=args.diff, report_dir=report_dir)
            try:
                display_path: Path | str = path.relative_to(root)
            except ValueError:
                display_path = path
            print(f"Wrote drift report: {display_path}")
            return 0

        if args.command == "run":
            if args.run_command == "start":
                state = start_run(
                    root,
                    Path(args.context_pack),
                    run_id=args.run_id,
                    max_iterations=args.max_iterations,
                    mode=args.mode,
                    run_dir=_run_dir_from_args(args),
                )
                print(
                    f"Started run {state['run_id']} for {state['context_pack']} "
                    f"(mode={state.get('mode', 'supervised')}, max_iterations={state['max_iterations']})."
                )
                return 0
            if args.run_command == "resume":
                result = resume_run(
                    root,
                    args.run_id,
                    executor_output=args.executor_output,
                    touched_paths=args.touched_path,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    run_dir=_run_dir_from_args(args),
                )
                review = result["review"]
                print(f"{args.run_id}: {review['decision']} ({review['confidence']}) - {review['reason']}")
                message = review.get("message_to_executor")
                if message:
                    print(message)
                return 0
            if args.run_command == "loop":
                result = loop_run(
                    root,
                    Path(args.context_pack) if args.context_pack else None,
                    run_id=args.run_id,
                    executor_output=args.executor_output,
                    touched_paths=args.touched_path,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    task_type=args.task_type,
                    order=args.order,
                    max_iterations=args.max_iterations,
                    mode=args.mode,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                    return 0

                state = result["state"]
                selected = result.get("selected_task")
                if selected:
                    print(f"Selected {selected['path']}.")
                action = "Started" if result.get("started") else "Using"
                print(f"{action} run {state['run_id']} for {state['context_pack']}.")
                target_writes = result.get("target_write_requirements")
                if target_writes:
                    print(
                        "Research findings may still require target writes: "
                        + ", ".join(target_writes)
                    )

                review = result.get("review")
                if review:
                    print(f"{state['run_id']}: {review['decision']} ({review['confidence']}) - {review['reason']}")
                    message = review.get("message_to_executor")
                    if message:
                        print(message)
                else:
                    print(f"Status: {state['status']}.")
                _print_session_preflight_summary(result.get("session_preflight"))
                return 0
            if args.run_command == "step":
                result = step_run(
                    root,
                    Path(args.context_pack) if args.context_pack else None,
                    run_id=args.run_id,
                    executor_output=args.executor_output,
                    touched_paths=args.touched_path,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    task_type=args.task_type,
                    order=args.order,
                    max_iterations=args.max_iterations,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                    return 0
                print(f"{result['run_id']}: {result['next_action']} ({result['state']['status']})")
                if result.get("prompt"):
                    print(result["prompt"])
                return 0
            if args.run_command == "package":
                package = package_run(
                    root,
                    Path(args.context_pack) if args.context_pack else None,
                    runner=args.runner,
                    run_id=args.run_id,
                    executor_output=args.executor_output,
                    touched_paths=args.touched_path,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    task_type=args.task_type,
                    order=args.order,
                    max_iterations=args.max_iterations,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(package, indent=2))
                    return 0
                print(f"{package['run_id']}: {package['next_action']} runner={package['runner']}")
                stdin = package.get("execution", {}).get("stdin")
                if stdin:
                    print(stdin)
                return 0
            if args.run_command == "result":
                raw_result = sys.stdin.read() if args.result_json == "-" else args.result_json
                result_payload = json.loads(raw_result)
                package = submit_runner_result(
                    root,
                    args.run_id,
                    result_payload,
                    runner=args.runner,
                    reviewer_mode=args.reviewer_mode,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(package, indent=2))
                    return 0
                print(f"{package['run_id']}: {package['next_action']} runner={package['runner']}")
                stdin = package.get("execution", {}).get("stdin")
                if stdin:
                    print(stdin)
                return 0
            if args.run_command == "demo":
                demo = run_demo(
                    root,
                    Path(args.context_pack) if args.context_pack else None,
                    runner=args.runner,
                    run_id=args.run_id,
                    executor_output=args.executor_output,
                    touched_paths=args.touched_path or None,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    task_type=args.task_type,
                    order=args.order,
                    max_iterations=args.max_iterations,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(demo, indent=2))
                    return 0
                print(f"{demo['run_id']}: {demo['final_next_action']} runner={demo['runner']}")
                return 0
            if args.run_command == "exec":
                result = execute_runner(
                    root,
                    Path(args.context_pack) if args.context_pack else None,
                    runner=args.runner,
                    command=_runner_command_from_args(args.runner_command, args.command_json),
                    run_id=args.run_id,
                    touched_paths=args.touched_path or None,
                    test_status=args.test_status,
                    reviewer_mode=args.reviewer_mode,
                    task_type=args.task_type,
                    order=args.order,
                    max_iterations=args.max_iterations,
                    timeout_seconds=args.timeout,
                    run_dir=_run_dir_from_args(args),
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                    return 0
                print(f"{result['run_id']}: {result['final_next_action']} runner={result['runner']}")
                return 0
            if args.run_command == "inspect":
                info = inspect_run(root, args.run_id, run_dir=_run_dir_from_args(args))
                print(json.dumps(info, indent=2))
                return 0
            if args.run_command == "prompt":
                handoff = build_next_executor_prompt(root, args.run_id, run_dir=_run_dir_from_args(args))
                if args.json:
                    print(json.dumps(handoff, indent=2))
                else:
                    print(handoff["prompt"])
                return 0
            if args.run_command == "abort":
                state = abort_run(root, args.run_id, reason=args.reason, run_dir=_run_dir_from_args(args))
                print(f"Aborted run {state['run_id']}.")
                return 0
            parser.print_help()
            return 0

        if args.command == "dcr":
            if args.dcr_command == "create":
                path = create_dcr_stub(
                    root,
                    title=args.title,
                    classification=args.classification,
                    dcr_id=args.dcr_id_override,
                )
                rel_path = path.relative_to(root)
                guidance = build_post_artifact_guidance(root, rel_path)
                if args.json:
                    print(
                        json.dumps(
                            {
                                "schema": "agentspec.dcr_create_result.v0",
                                "path": str(rel_path),
                                "guidance": guidance,
                            },
                            indent=2,
                        )
                    )
                    return 0
                display = guidance["agent_display"]
                print(f"Created DCR: {rel_path}")
                print(f"Next: {display['guidance']}")
                if display.get("prompt"):
                    print(f"Prompt: {display['prompt']}")
                _print_artifact_preservation(guidance.get("preservation"))
                return 0
            if args.dcr_command == "classify":
                path = set_classification(root, args.dcr_id, args.classification)
                print(f"Classified {args.dcr_id} as {args.classification}: {path.relative_to(root)}")
                return 0
            if args.dcr_command == "accept":
                accept_dcr(root, args.dcr_id)
                print(
                    f"Accepted {args.dcr_id}. "
                    f"Use `agentspec requirement accept <R-id>` to flip its requirements individually."
                )
                return 0
            if args.dcr_command == "list":
                for record in list_dcrs(root):
                    rel = Path(record["path"]).relative_to(root) if Path(record["path"]).is_absolute() else record["path"]
                    print(f"{record['id']}\t{record['classification']}\t{record['status']}\t{rel}")
                return 0
            parser.print_help()
            return 0

        if args.command == "requirement":
            if args.requirement_command == "accept":
                info = accept_requirement(root, args.requirement_id)
                origin = info.get("originating_dcr")
                suffix = f" (originating_dcr={origin})" if origin else ""
                print(f"Accepted {args.requirement_id}{suffix}.")
                return 0
            parser.print_help()
            return 0

        if args.command == "dogfood":
            if args.dogfood_command == "record":
                from datetime import date
                from .paths import slugify
                slug = slugify(args.slug)
                today = date.today().isoformat()
                target = root / "reports" / "dogfood" / f"{today}-{slug}.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise FileExistsError(f"Dogfood note already exists: {target}")
                body = (
                    f"# {args.title}\n\n"
                    f"Recorded: {today}\n\n"
                    f"## Context\n\n"
                    f"<!-- where this finding came from -->\n\n"
                    f"## Observation\n\n"
                    f"<!-- what happened, what surprised you -->\n\n"
                    f"## Implication\n\n"
                    f"<!-- what AgentSpec should learn or do differently -->\n\n"
                    f"## Suggested Next Step\n\n"
                    f"<!-- DCR? open question? backlog item? nothing yet? -->\n"
                )
                target.write_text(body, encoding="utf-8")
                print(f"Recorded: {target.relative_to(root)}")
                return 0
            parser.print_help()
            return 0

        if args.command == "mcp" and args.mcp_command == "serve":
            print("MCP server is not implemented in this MVP. Use generated artifacts and CLI commands for now.")
            return 2

        parser.print_help()
        return 0
    except Exception as exc:
        display_error = _structured_error_for_exception(exc, args)
        get_logger().error("CLI command failed: %s", display_error)
        if getattr(args, "json", False):
            print(json.dumps(_build_error_envelope(display_error, parser.prog, args), indent=2))
        else:
            print(_format_plain_error(display_error, parser.prog), file=sys.stderr)
        return 1


CLI_ERROR_SCHEMA = "agentspec.cli_error.v0"

# Exception classes treated as transient by harness consumers. Default for
# everything else is False — most CLI failures are user input or schema
# errors that retrying would just hit again.
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, AgentSpecError):
        return exc.effective_retryable
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def _build_error_envelope(exc: BaseException, prog: str, args: argparse.Namespace) -> dict[str, Any]:
    structured = _structured_error_for_exception(exc, args)
    envelope = {
        "schema": CLI_ERROR_SCHEMA,
        "error": {
            "type": getattr(structured, "type_name", None) or type(structured).__name__,
            "message": str(structured),
            "retryable": _is_retryable(structured),
            "command": _command_label(args, prog),
        },
    }
    to_dict = getattr(structured, "to_dict", None)
    if callable(to_dict):
        details = to_dict()
        if isinstance(structured, AgentSpecError):
            envelope["error"].update(details)
        else:
            envelope["error"]["details"] = details
    return envelope


def _structured_error_for_exception(exc: BaseException, args: argparse.Namespace) -> BaseException:
    if isinstance(exc, AgentSpecError):
        return exc
    operation = _operation_label(args)
    recovery_command = _recovery_command_for_args(args)
    run_id = getattr(args, "run_id", None)
    details = {"mutation": "none"}
    if isinstance(run_id, str) and run_id:
        details["run_id"] = run_id
    message = str(exc)
    if isinstance(exc, FileNotFoundError) and message.startswith("Run not found:"):
        return RunStateNotFoundError(
            message,
            operation=operation,
            recovery_command=recovery_command,
            details=details,
            type_name=type(exc).__name__,
        )
    if isinstance(exc, ValueError) and message.startswith("Invalid run_id:"):
        return AgentSpecValidationError(
            message,
            operation=operation,
            recovery_command=recovery_command,
            details=details,
            type_name=type(exc).__name__,
        )
    if isinstance(exc, ValueError) and operation == "run.result":
        return RunnerResultInvalidError(
            message,
            operation=operation,
            recovery_command=recovery_command,
            details=details,
            type_name=type(exc).__name__,
        )
    if isinstance(exc, PermissionError):
        return AgentSpecIOPermissionError(
            message,
            operation=operation,
            recovery_command=recovery_command,
            details=details,
            type_name=type(exc).__name__,
        )
    return exc


def _operation_label(args: argparse.Namespace) -> str | None:
    command = getattr(args, "command", None)
    if not command:
        return None
    subcommand = (
        getattr(args, f"{command}_command", None)
        or getattr(args, "run_command", None)
        or getattr(args, "review_command", None)
        or getattr(args, "task_command", None)
        or getattr(args, "dcr_command", None)
        or getattr(args, "intake_command", None)
        or getattr(args, "source_command", None)
    )
    if subcommand:
        return f"{command}.{subcommand}"
    return str(command)


def _recovery_command_for_args(args: argparse.Namespace) -> str | None:
    if getattr(args, "command", None) == "run" and getattr(args, "run_command", None) == "result":
        run_id = getattr(args, "run_id", None)
        runner = getattr(args, "runner", None) or "generic"
        if isinstance(run_id, str) and run_id:
            return f"aspec run package --runner {runner} --run-id {run_id} --json"
    if getattr(args, "command", None) == "run":
        return "aspec status --json"
    return None


def _format_plain_error(exc: BaseException, prog: str) -> str:
    if isinstance(exc, AgentSpecError):
        code = exc.to_dict().get("code")
        lines = [f"{prog}: error: [{code}] {exc}"]
        if exc.recovery_command:
            lines.append(f"Recovery: {exc.recovery_command}")
        return "\n".join(lines)
    return f"{prog}: error: {exc}"


def _command_label(args: argparse.Namespace, prog: str) -> str:
    parts = [prog]
    cmd = getattr(args, "command", None)
    if cmd:
        parts.append(str(cmd))
    return " ".join(parts)


def _print_finish_result(result: dict[str, Any]) -> None:
    context_pack = result.get("context_pack", "-")
    if result.get("dry_run"):
        status = "finishable" if result.get("finishable") else "needs attention"
        print(f"Finish dry-run for {context_pack}: {status} (enforcement={result.get('enforcement')}).")
    else:
        print(f"Finished {context_pack} via run {result.get('run_id')}.")
    for finding in result.get("findings", []):
        if not isinstance(finding, dict):
            continue
        message = finding.get("message") or finding.get("type") or "Finish finding"
        print(f"Warning: {message}")
        repair = finding.get("repair") or finding.get("recommendation")
        if repair:
            print(f"Repair: {repair}")


def _print_artifact_preservation(preservation: object) -> None:
    text = format_artifact_preservation_guidance(preservation)
    if text:
        print(text)


def _print_session_preflight_summary(preflight: Any) -> None:
    if not isinstance(preflight, dict):
        return
    if preflight.get("status") in {"blocked", "missing"}:
        print(f"Session preflight: {preflight.get('message')}")
        command = preflight.get("recommended_command")
        if command:
            print(f"Next: {command}")
    elif preflight.get("status") == "satisfied" and preflight.get("satisfied_by") == "explicit_host_worktree":
        print("Session preflight: explicit host-worktree execution declared.")


def _print_no_ready_task(summary: dict[str, Any], warnings: list[str]) -> None:
    action = summary.get("recommended_next_action") if isinstance(summary.get("recommended_next_action"), dict) else {}
    commands = action.get("commands") if isinstance(action.get("commands"), list) else []
    options = action.get("options") if isinstance(action.get("options"), list) else []
    reason = action.get("reason") or summary.get("main_point") or "No ready task context pack found."
    print("No ready task context pack found.")
    print(f"Why: {reason}")
    print(f"Recommended next action: {action.get('label', 'Prepare the next AgentSpec task context pack.')}")
    if commands:
        print("Terminal next commands:")
        for command in commands:
            print(f"- {command}")
    if options:
        print("Next options:")
        for index, option in enumerate(options, start=1):
            if not isinstance(option, dict):
                continue
            print(f"{index}. {option.get('label', f'Option {index}')}")
            when = option.get("when")
            if when:
                print(f"   Use when: {when}")
            option_commands = option.get("commands") if isinstance(option.get("commands"), list) else []
            for command in option_commands:
                print(f"   - {command}")
    if warnings:
        print("Workflow warnings:")


def _task_next_no_ready_summary(summary: dict[str, Any], task_type: str | None) -> dict[str, Any]:
    if not task_type:
        return summary
    main_point = f"No {task_type} task context pack is ready."
    blocked_by = summary.get("blocked_by") if isinstance(summary.get("blocked_by"), list) else []
    updated = dict(summary)
    action = {
        "label": f"Create or select a ready {task_type} task context pack.",
        "human_decision_required": True,
        "reason": f"The --type {task_type} filter excludes all currently ready context packs.",
        "commands": [
            f"aspec task list --type {task_type}",
            f'aspec task create --type {task_type} --title "Prepare {task_type} work"',
            "aspec status --json",
        ],
    }
    action["agent_display"] = agent_display_for_next_action(action)
    updated.update(
        {
            "main_point": main_point,
            "current_stage": "task_type_unavailable",
            "current_artifact": None,
            "recommended_next_action": action,
            "blocked_by": [
                {
                    "kind": "no_ready_task_type",
                    "message": main_point,
                    "task_type": task_type,
                },
                *blocked_by,
            ],
        }
    )
    return updated


def _dispatch_next_action(root: Path) -> int:
    status_payload = build_project_status(root)
    runs = status_payload.get("runs") if isinstance(status_payload.get("runs"), dict) else {}
    tasks = status_payload.get("tasks") if isinstance(status_payload.get("tasks"), dict) else {}

    attention_runs = runs.get("attention") if isinstance(runs, dict) else []
    if isinstance(attention_runs, list) and attention_runs:
        run_id = str(attention_runs[0].get("run_id"))
        info = inspect_run(root, run_id)
        print(json.dumps(info, indent=2))
        return 0

    active_runs = runs.get("active") if isinstance(runs, dict) else []
    if isinstance(active_runs, list) and active_runs:
        run_id = str(active_runs[0].get("run_id"))
        handoff = build_next_executor_prompt(root, run_id)
        print(handoff["prompt"])
        return 0

    next_task = tasks.get("next") if isinstance(tasks, dict) else None
    if isinstance(next_task, dict) and next_task.get("path"):
        result = loop_run(root, Path(str(next_task["path"])))
        selected = result.get("selected_task")
        if selected:
            print(f"Selected {selected['path']}.")
        state = result["state"]
        action = "Started" if result.get("started") else "Using"
        print(f"{action} run {state['run_id']} for {state['context_pack']}.")
        review = result.get("review")
        if review:
            print(f"{state['run_id']}: {review['decision']} ({review['confidence']}) - {review['reason']}")
            message = review.get("message_to_executor")
            if message:
                print(message)
        else:
            print(f"Status: {state['status']}.")
        return 0

    summary = status_payload.get("lifecycle_summary") if isinstance(status_payload.get("lifecycle_summary"), dict) else {}
    workflows = status_payload.get("workflows") if isinstance(status_payload.get("workflows"), dict) else {}
    _print_no_ready_task(summary, workflow_warning_lines(workflows))
    return 1


def _runner_command_from_args(command: str | None, command_json: str | None) -> list[str] | None:
    if command and command_json:
        raise ValueError("Use either --command or --command-json, not both.")
    if command_json:
        parsed = json.loads(command_json)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("--command-json must be a JSON array of strings.")
        return parsed
    if command:
        return shlex.split(command)
    return None


def _run_dir_from_args(args: argparse.Namespace) -> Path | None:
    value = getattr(args, "run_dir", None)
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
