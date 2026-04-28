from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compile import compile_project
from .dcr import (
    ALLOWED_CLASSIFICATIONS,
    accept_dcr,
    create_dcr_stub,
    list_dcrs,
    set_classification,
)
from .doctor import run_doctor
from .drift import run_drift
from .emit import emit_targets
from .ingest import ingest_source
from .init import init_project
from .io import load_data
from .requirement import accept_requirement
from .run import abort_run, build_next_executor_prompt, complete_context_pack_run, inspect_run, loop_run, resume_run, start_run, step_run
from .task import create_task_context_pack, list_task_context_packs, next_task_context_pack


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

    ingest = subparsers.add_parser("ingest", help="Import and sectionize a Markdown source document.")
    ingest.add_argument("path")
    ingest.add_argument("--classification", default="internal", choices=["public", "internal", "confidential", "restricted"])
    ingest.add_argument("--storage-mode", default="committed", choices=["committed", "local-secure-cache", "enterprise-object-store", "pointer-only"])

    subparsers.add_parser("compile", help="Compile source sections into specs, requirements, assumptions, questions, and readiness.")

    readiness = subparsers.add_parser("readiness", help="Print readiness score.")
    readiness.add_argument("--json", action="store_true")

    subparsers.add_parser("doctor", help="Run read-only brownfield assessment.")

    repo = subparsers.add_parser("repo", help="Repository utilities.")
    repo_subparsers = repo.add_subparsers(dest="repo_command")
    repo_subparsers.add_parser("scan", help="Alias for doctor.")

    task = subparsers.add_parser("task", help="Task utilities.")
    task_subparsers = task.add_subparsers(dest="task_command")
    task_create = task_subparsers.add_parser("create", help="Create a task context pack.")
    task_create.add_argument("--requirement")
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
    task_complete.add_argument("--json", action="store_true")

    context = subparsers.add_parser("context", help="Context pack utilities.")
    context_subparsers = context.add_subparsers(dest="context_command")
    context_build = context_subparsers.add_parser("build", help="Create a task context pack.")
    context_build.add_argument("--requirement")
    context_build.add_argument("--type", default="implementation")
    context_build.add_argument("--title")

    emit = subparsers.add_parser("emit", help="Generate agent integration artifacts.")
    emit.add_argument("--target", default="agents-md", help="Comma-separated targets: agents-md,claude,codex,github-actions,all")

    drift = subparsers.add_parser("drift", help="Generate a spec drift review report.")
    drift.add_argument("--diff")

    run = subparsers.add_parser("run", help="Supervised run utilities.")
    run_subparsers = run.add_subparsers(dest="run_command")
    run_start = run_subparsers.add_parser("start", help="Create local supervised-run state for a context pack.")
    run_start.add_argument("context_pack")
    run_start.add_argument("--run-id")
    run_start.add_argument("--max-iterations", type=int)

    run_resume = run_subparsers.add_parser("resume", help="Record an executor iteration and reviewer verdict.")
    run_resume.add_argument("run_id")
    run_resume.add_argument("--executor-output", required=True)
    run_resume.add_argument("--touched-path", action="append", default=[])
    run_resume.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_resume.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])

    run_loop = run_subparsers.add_parser("loop", help="Select, start, or resume the next supervised run step.")
    run_loop.add_argument("context_pack", nargs="?")
    run_loop.add_argument("--run-id")
    run_loop.add_argument("--executor-output")
    run_loop.add_argument("--touched-path", action="append", default=[])
    run_loop.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_loop.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_loop.add_argument("--type", dest="task_type")
    run_loop.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_loop.add_argument("--max-iterations", type=int)
    run_loop.add_argument("--json", action="store_true")

    run_step = run_subparsers.add_parser("step", help="Run one harness control-plane step.")
    run_step.add_argument("context_pack", nargs="?")
    run_step.add_argument("--run-id")
    run_step.add_argument("--executor-output")
    run_step.add_argument("--touched-path", action="append", default=[])
    run_step.add_argument("--test-status", default="not_run", choices=["not_run", "passed", "failed"])
    run_step.add_argument("--reviewer", dest="reviewer_mode", choices=["deterministic", "model", "auto"])
    run_step.add_argument("--type", dest="task_type")
    run_step.add_argument("--order", default="newest", choices=["oldest", "newest"])
    run_step.add_argument("--max-iterations", type=int)
    run_step.add_argument("--json", action="store_true")

    run_inspect = run_subparsers.add_parser("inspect", help="Print current supervised-run state.")
    run_inspect.add_argument("run_id")

    run_prompt = run_subparsers.add_parser("prompt", help="Print the next executor handoff prompt.")
    run_prompt.add_argument("run_id")
    run_prompt.add_argument("--json", action="store_true")

    run_abort = run_subparsers.add_parser("abort", help="Abort a supervised run.")
    run_abort.add_argument("run_id")
    run_abort.add_argument("--reason", default="Aborted by user.")

    dcr = subparsers.add_parser("dcr", help="Design Change Request utilities.")
    dcr_subparsers = dcr.add_subparsers(dest="dcr_command")

    dcr_create = dcr_subparsers.add_parser("create", help="Create a new DCR document.")
    dcr_create.add_argument("--title", required=True)
    dcr_create.add_argument("--classification", required=True, choices=sorted(ALLOWED_CLASSIFICATIONS))
    dcr_create.add_argument("--id", dest="dcr_id_override", help="Override the auto-numbered DCR id (e.g. DCR-0099).")

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

    mcp = subparsers.add_parser("mcp", help="MCP utilities.")
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command")
    serve = mcp_subparsers.add_parser("serve", help="MVP placeholder for future MCP server.")
    serve.add_argument("--stdio", action="store_true")
    serve.add_argument("--http")

    return parser


def main(argv: list[str] | None = None, prog: str | None = None) -> int:
    parser = build_parser(prog=prog)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "init":
            written = init_project(root, mode=args.mode, targets=args.targets, archetype=args.archetype)
            print(f"Initialized AgentSpec workspace at {root} ({len(written)} files created).")
            return 0

        if args.command == "ingest":
            result = ingest_source(root, Path(args.path), classification=args.classification, storage_mode=args.storage_mode)
            print(f"Ingested {result['source']['uri']} as {result['source']['id']} with {len(result['sections'])} sections.")
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

        if args.command == "doctor" or (args.command == "repo" and args.repo_command == "scan"):
            scan = run_doctor(root)
            print(f"Doctor scan complete: {root / 'reports' / 'doctor' / 'repo-scan.yml'}")
            print(f"Languages: {', '.join(scan['repo']['languages']) or '-'}")
            return 0

        if args.command == "task" and args.task_command == "create":
            path = create_task_context_pack(root, requirement_id=args.requirement, task_type=args.type, title=args.title)
            print(f"Created task context pack: {path.relative_to(root)}")
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
                print("No ready task context pack found.")
                return 1
            if args.json:
                print(json.dumps(record, indent=2))
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
            )
            if args.json:
                print(json.dumps(state, indent=2))
            else:
                print(f"Marked {state['context_pack']} complete via run {state['run_id']}.")
            return 0

        if args.command == "context" and args.context_command == "build":
            path = create_task_context_pack(root, requirement_id=args.requirement, task_type=args.type, title=args.title)
            print(f"Created task context pack: {path.relative_to(root)}")
            return 0

        if args.command == "emit":
            written = emit_targets(root, args.target)
            print(f"Emitted {len(written)} integration artifacts.")
            return 0

        if args.command == "drift":
            path = run_drift(root, diff_ref=args.diff)
            print(f"Wrote drift report: {path.relative_to(root)}")
            return 0

        if args.command == "run":
            if args.run_command == "start":
                state = start_run(
                    root,
                    Path(args.context_pack),
                    run_id=args.run_id,
                    max_iterations=args.max_iterations,
                )
                print(
                    f"Started run {state['run_id']} for {state['context_pack']} "
                    f"(max_iterations={state['max_iterations']})."
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

                review = result.get("review")
                if review:
                    print(f"{state['run_id']}: {review['decision']} ({review['confidence']}) - {review['reason']}")
                    message = review.get("message_to_executor")
                    if message:
                        print(message)
                else:
                    print(f"Status: {state['status']}.")
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
                )
                if args.json:
                    print(json.dumps(result, indent=2))
                    return 0
                print(f"{result['run_id']}: {result['next_action']} ({result['state']['status']})")
                if result.get("prompt"):
                    print(result["prompt"])
                return 0
            if args.run_command == "inspect":
                info = inspect_run(root, args.run_id)
                print(json.dumps(info, indent=2))
                return 0
            if args.run_command == "prompt":
                handoff = build_next_executor_prompt(root, args.run_id)
                if args.json:
                    print(json.dumps(handoff, indent=2))
                else:
                    print(handoff["prompt"])
                return 0
            if args.run_command == "abort":
                state = abort_run(root, args.run_id, reason=args.reason)
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
                print(f"Created DCR: {path.relative_to(root)}")
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

        if args.command == "mcp" and args.mcp_command == "serve":
            print("MCP server is not implemented in this MVP. Use generated artifacts and CLI commands for now.")
            return 2

        parser.print_help()
        return 0
    except Exception as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
