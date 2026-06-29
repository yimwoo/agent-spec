"""Source connector contracts and the local Confluence fixture adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class FetchedSource:
    """Normalized source content returned by a connector provider."""

    body: str
    remote_uri: str
    remote_version: str | None = None
    fetched_at: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorFetchError(ValueError):
    """Raised when a source connector cannot retrieve or parse a source."""

    def __init__(self, connector: str, uri: str, message: str):
        self.connector = connector
        self.uri = uri
        self.message = message
        super().__init__(f"{connector} connector failed for {uri}: {message}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize connector failure context for command output."""

        return {
            "connector": self.connector,
            "uri": self.uri,
            "message": self.message,
        }


def fetch_source(kind: str, uri: str) -> FetchedSource:
    """Fetch a source through the registered connector for its kind.

    Raises:
        ConnectorFetchError: If no provider exists or retrieval fails.
    """

    if kind == "confluence":
        return _fetch_confluence_fixture(uri)
    raise ConnectorFetchError(kind, uri, "No connector provider is registered.")


def _fetch_confluence_fixture(uri: str) -> FetchedSource:
    path = Path(uri)
    if not path.exists():
        raise ConnectorFetchError(
            "confluence",
            uri,
            "This MVP connector expects a local JSON fixture.",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConnectorFetchError(
            "confluence",
            uri,
            f"Fixture is not valid JSON: {exc.msg}.",
        ) from exc
    if not isinstance(payload, dict):
        raise ConnectorFetchError("confluence", uri, "Fixture must be a JSON object.")

    body = payload.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ConnectorFetchError(
            "confluence",
            uri,
            "Fixture must include a non-empty string body.",
        )

    remote_uri = payload.get("remote_uri") or payload.get("uri") or uri
    remote_version = payload.get("remote_version") or payload.get("version")
    fetched_at = payload.get("fetched_at")
    title = payload.get("title")
    return FetchedSource(
        body=body,
        remote_uri=str(remote_uri),
        remote_version=str(remote_version) if remote_version is not None else None,
        fetched_at=str(fetched_at) if fetched_at is not None else None,
        title=str(title) if title is not None else None,
        metadata={
            key: value
            for key, value in payload.items()
            if key
            not in {"body", "remote_uri", "uri", "remote_version", "version", "fetched_at", "title"}
        },
    )
