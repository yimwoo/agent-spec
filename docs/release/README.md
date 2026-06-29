# Release Evidence

AgentSpec can keep task runtime state under `agent/` private while publishing a
small, reviewable completion record in `docs/release/evidence.yml`. The public
artifact preserves release, verification, and code-review evidence after local
task ledgers, context packs, reviews, runs, and sessions are cleaned up.

## When Evidence Is Written

Task completion writes public evidence when either condition is true:

- Git ignores the untracked `agent/task-ledger.yml` path.
- `docs/release/evidence.yml` already exists, so later completions continue the
  established public history.

Recording a later code review refreshes the matching completed task entry. The
`code_review` field always identifies the latest review, while `reviews` keeps
the ordered, deduplicated review history. A later `not-ready` verdict therefore
supersedes an earlier passing verdict for maturity checks without deleting the
earlier audit record.

## Schema Contract

The current schema is `agentspec.release_evidence.v0`. Each task entry must
contain:

- a matching `task_id` and `context_pack` key;
- `status: complete`;
- a non-empty completion `run_id` and `updated_at` timestamp;
- a verification status of `passed`, `failed`, or `not_run`;
- when present, a review ID matching `REVIEW-<number>` and a verdict of
  `ready`, `ready-with-warnings`, or `not-ready`.

AgentSpec ignores unsupported schemas and malformed task or review records.
Governed maturity accepts public review evidence only when the latest verdict
is `ready` or `ready-with-warnings`, and accepts test evidence only when the
verification status is `passed`.

The file is a projection, not an editable approval mechanism. Produce or update
it through task completion and code-review commands so private and public
evidence remain consistent.

## Private-State Cleanup

After the public file is committed, local `agent/` state may be removed without
losing the projected completion, test, and review history. Paths stored in the
artifact are audit identifiers; the referenced private files do not need to
remain tracked or present. Teams should review context-pack titles and reviewer
identifiers before publishing because those values become repository history.

## Release Verification

`.github/workflows/release.yml` runs version synchronization, the Python test
suite, bytecode compilation, configured mypy and pylint checks, package builds,
and artifact metadata validation on relevant pull requests. Published releases
and manual dispatches additionally verify that the requested tag matches the
package version and checkout commit, and that the GitHub release contains the
expected source and wheel artifacts.

Before publishing, merge a green pull request and create the version tag from
that verified commit. After publication, the release event provides the final
tag and asset audit.
