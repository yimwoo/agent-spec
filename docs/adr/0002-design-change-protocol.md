# ADR-0002: Design Change Protocol — DCRs Are First-Class Artifacts

Status: accepted
Date: 2026-04-28
Supersedes (in part): the line in `D-11.4 Dogfood Mode` that says AgentSpec
"records design changes as ADRs"
Related: `DCR-0002-design-change-management.md`, `DCR-0001-supervised-runs.md`

## Context

After initial ingestion of `docs/source/src-0001-agentspec-design-doc.md` and
the start of implementation, design updates have begun arriving from the
project owner (DCR-0001 and DCR-0002 themselves are the first two). The
current architecture has no canonical artifact for capturing such updates.
Direct edits to the canonical source would invalidate content hashes
(D-12.4) and break traceability. ADRs alone conflate intake with decision
recording. The dogfood goal (D-11.4) cannot close honestly without a
formal lane.

## Decision

AgentSpec adopts a **Design Change Request (DCR)** protocol as the entry
point for any design update arriving after the canonical source snapshot
is taken.

Concretely:

1. **DCRs are first-class artifacts.** They live in
   `docs/change-requests/` as `DCR-NNNN-<slug>.md` files with a fixed
   shape: status, classification, source-section references, impact
   assessment, proposed requirements, disposition, acceptance criteria.
2. **Every incoming change goes through a DCR.** This includes ideas from
   the project owner, findings from supervised runs, drift-review
   recommendations, and externally proposed changes.
3. **Classification is a five-value enum.** A DCR is exactly one of:
   `implement-now`, `defer`, `spike`, `reject`, `needs-adr`.
   Combinations (e.g., `spike` plus a follow-up `needs-adr`) are expressed
   by required follow-ups, not by multi-classification.
4. **DCRs are gating, not advisory.** A task context pack derived from a
   DCR must cite the DCR ID and may not be created until the DCR is in an
   implementation-eligible state (`implement-now`, or `needs-adr` with the
   ADR accepted). Drive-by code changes that bypass this lane are a drift
   violation.
5. **Requirements introduced by a DCR carry a new status:
   `proposed-pending-acceptance`.** Such requirements are visible in
   `requirements.yml` for traceability but are not promoted to `accepted`
   until the originating DCR is accepted. This adds a value to the
   requirement-status enum implied by D-18.
6. **ADRs are reserved for architectural decisions.** A DCR classified
   `needs-adr` produces an ADR; a DCR classified `implement-now` does not
   need one unless the change involves a load-bearing architectural choice.
7. **The canonical source document is not edited in place.** When a DCR
   demands new design-doc sections (e.g., new `D-*` anchors), they are
   added by re-ingesting the design doc as a *new* source snapshot
   (e.g., `src-0002-...`). The previous snapshot remains intact, hashes
   and all.

## Consequences

### Positive

- Incoming design ideas have a single, auditable lane.
- Traceability gains a new axis: requirement → originating DCR → originating
  source section. Drift reviews can blame the right artifact.
- Dogfood Mode honestly closes its own loop: the project records its own
  design changes the same way it expects user projects to.
- The "explicit uncertainty" principle (D-07) is enforced at intake, not
  after the fact.
- Risky changes (architectural, security, supervised execution) get
  routed through the right rigor (`spike` and/or `needs-adr`) rather than
  silently slipping into a context pack.

### Negative / Costs

- One additional artifact directory and intake step per change. Small but
  non-zero overhead for trivial changes.
- The DCR template and the requirement-status enum become schema surface
  that the validation model (R-008) must support. Tracked by R-121..R-124.
- DCR numbering policy is unresolved (Q-015): global vs. namespaced. We
  default to **globally sequential** until the first cross-area conflict
  forces a different scheme.

### Neutral

- Existing ADRs (ADR-0001) are unaffected. They continue to describe
  architectural decisions; ADR-0002 simply reorganizes how new ones are
  triggered.

## Compliance with existing principles (D-07)

- **Source-backed over summary-backed:** DCRs cite `D-*` anchors and link
  proposed requirements to existing ones.
- **Explicit uncertainty:** open questions raised by a DCR are recorded
  in `open-questions.yml` at intake time.
- **Context pack as work unit:** DCRs gate context-pack creation; they do
  not replace it.
- **Shared state through files, not chat history:** DCRs are files,
  reviewed and accepted by file diff.

## Status of this ADR

Accepted on 2026-04-28 by yimwu, drafted by Claude pilot agent during the
DCR-0002 intake.
