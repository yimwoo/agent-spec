"""Single-requirement acceptance per DCR-0004 / R-134.

The `accept_requirement` function is the canonical way to flip a DCR-derived
requirement from `proposed-pending-acceptance` to `accepted`. It enforces:

- the requirement exists in `docs/traceability/requirements.yml`
- it is currently in `proposed-pending-acceptance`
- if `originating_dcr` is set, the originating DCR is itself `accepted`

The cascade behavior previously living in `dcr accept` is intentionally not
present here: each requirement is flipped explicitly, typically because its
implementation pack has shipped and verified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dcr import find_dcr_by_id, parse_dcr
from .io import load_data, write_data


def accept_requirement(root: Path, requirement_id: str) -> dict[str, Any]:
    """Accept one eligible requirement and persist the updated registry.

    Raises:
        ValueError: If the requirement is missing, ineligible, or already
            accepted.
    """

    reqs_path = Path(root) / "docs" / "traceability" / "requirements.yml"
    requirements = load_data(reqs_path, []) or []

    target: dict[str, Any] | None = None
    for requirement in requirements:
        if requirement.get("id") == requirement_id:
            target = requirement
            break
    if target is None:
        raise ValueError(f"Requirement not found: {requirement_id}")

    current_status = target.get("status")
    if current_status == "accepted":
        raise ValueError(
            f"Cannot accept {requirement_id}: status is already 'accepted'."
        )
    if current_status != "proposed-pending-acceptance":
        raise ValueError(
            f"Cannot accept {requirement_id}: status is {current_status!r}, "
            f"expected 'proposed-pending-acceptance'."
        )

    originating_dcr = target.get("originating_dcr")
    if originating_dcr:
        dcr_path = find_dcr_by_id(root, originating_dcr)
        if dcr_path is None:
            raise ValueError(
                f"Cannot accept {requirement_id}: originating DCR {originating_dcr} not found "
                f"in docs/change-requests/."
            )
        dcr = parse_dcr(dcr_path)
        if dcr.get("status") != "accepted":
            raise ValueError(
                f"Cannot accept {requirement_id}: originating DCR {originating_dcr} "
                f"has status {dcr.get('status')!r}; must be 'accepted' first "
                f"(use `agentspec dcr accept {originating_dcr}`)."
            )

    target["status"] = "accepted"
    write_data(reqs_path, requirements)
    return {"requirement_id": requirement_id, "originating_dcr": originating_dcr}
