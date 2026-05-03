# Research Mode Review Evidence Contract Spike

Date: 2026-05-02
Originating DCR: DCR-0035
Requirement: R-171

## Decision

Use structured `acceptance_evidence` in runner results for research-mode
completion, and teach the reviewer path to consume it explicitly. Do not rely
on free-form `executor_output` wording as the only completion signal.

The first implementation slice should keep the existing
`agentspec.runner_result.v0` schema name and add an optional field. The field is
optional for supervised/implementation runs, but required when a research-mode
runner result asks to complete with `test_status=passed`.

## Problem

Research mode currently has two weak contracts:

- `parse_runner_result` accepts a minimal result with only `executor_output`,
  optional `touched_paths`, and `test_status`.
- `quality_reviewer_signoff` approves only when free-form executor output names
  acceptance evidence in the expected words.

That means a useful research result can be mechanically valid, write only inside
the research surface, and still halt because the reviewer cannot distinguish
"terse but evidenced" from "ambiguous completion claim."

## Proposed Evidence Shape

Add this optional field to runner results:

```json
{
  "acceptance_evidence": {
    "schema": "agentspec.research_acceptance_evidence.v0",
    "durable_artifacts": [
      "docs/change-requests/DCR-0037-example.md",
      "docs/discovery/open-questions.yml"
    ],
    "allowed_path_confirmation": true,
    "verification_commands": [
      {
        "command": "git diff --check",
        "status": "passed"
      },
      {
        "command": "aspec doctor",
        "status": "passed"
      }
    ],
    "covered_requirements": ["R-142"],
    "covered_questions": ["Q-024"],
    "source_checks": [
      "DCR parses with aspec dcr list",
      "Open question remains linked to originating evidence"
    ],
    "no_task_context_pack_reason": "Research mode intentionally produced proposal artifacts only."
  }
}
```

Minimum valid evidence for research completion:

- `durable_artifacts`: non-empty list of paths under the research write surface
  (`reports/dogfood/**`, `docs/discovery/open-questions.yml`,
  `docs/change-requests/**`);
- `allowed_path_confirmation`: `true`;
- `verification_commands`: non-empty list, every item has `status=passed`;
- either `covered_requirements`, `covered_questions`, or `source_checks` is
  non-empty;
- `no_task_context_pack_reason`: required when the result does not create a task
  context pack.

## Runtime Contract

Recommended implementation flow:

1. `build_runner_package` includes `acceptance_evidence` in the
   `report_back.result_template` when the active state is research mode.
2. `parse_runner_result` accepts and validates the optional
   `acceptance_evidence` object.
3. `submit_runner_result` loads the run state before review. If the run is
   research mode and `test_status=passed`, then missing or invalid evidence
   returns a structured CLI error before `resume_run` mutates state.
4. `resume_run` passes `acceptance_evidence` to reviewer functions and records
   it in the executor event.
5. `review_executor_output` may emit `complete` for research mode when
   `test_status=passed` and evidence is valid, even if the free-form output is
   terse.
6. `quality_reviewer_signoff` approves research completion when evidence is
   valid. It keeps the existing free-form acceptance-evidence rule for
   non-research autonomous runs.

This preserves the current reviewer model while making research-mode completion
deterministic.

## Test Plan

Add tests in the implementation DCR:

- `tests/test_runner_package.py`: research-mode runner packages include an
  `acceptance_evidence` result template.
- `tests/test_runner_package.py`: `aspec run result` rejects
  `test_status=passed` research results that omit `acceptance_evidence`, and
  the run state remains unchanged.
- `tests/test_research_mode.py`: a valid research-only proposal with durable
  artifacts, allowed-path confirmation, and passed verification completes even
  when `executor_output` is terse.
- `tests/test_research_mode.py`: an unclassified research pause without valid
  completion evidence still logs a finding and auto-continues.
- `tests/test_research_mode.py`: destructive git, credential patterns,
  forbidden paths, and auto-acceptance attempts still halt before any evidence
  can approve the run.

## Hard Limits

Hard limits stay ahead of the evidence contract. Evidence must not override:

- destructive git or remote push policy;
- credential leakage patterns;
- forbidden writes outside the active mode's allowed paths;
- auto-acceptance attempts such as `aspec requirement accept`.

The implementation should preserve the current `evaluate_policy` ordering:
policy verdict first, reviewer completion second.

## Implementation Slices

1. **Runner evidence schema and package template**
   - Add validation helper for `acceptance_evidence`.
   - Include the evidence template in research-mode runner packages.

2. **Result ingestion guard**
   - Reject passed research results without valid evidence before calling
     `resume_run`.
   - Preserve current behavior for supervised and implementation runs.

3. **Reviewer consumption**
   - Thread evidence into `resume_run`, `review_executor_output`, and
     `quality_reviewer_signoff`.
   - Approve research completion from valid evidence.

4. **Regression tests**
   - Add the test cases listed above.
   - Re-run the full suite and dogfood with an empty-queue autonomous research
     run.

## Follow-Up DCR

Create `DCR-0037: Implement research-mode acceptance evidence contract` as
`implement-now` after this spike is accepted. The implementation can be one
small task if scoped to `agentspec/runner.py`, `agentspec/run.py`,
`agentspec/review.py`, `tests/test_runner_package.py`, and
`tests/test_research_mode.py`.
