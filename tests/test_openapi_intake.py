"""Tests for OpenAPI/YAML intake and structural contract diff (T-051 / R-153)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data


BASELINE_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Payments API", "version": "1.0.0"},
    "components": {
        "securitySchemes": {
            "oauth": {
                "type": "oauth2",
                "flows": {"clientCredentials": {"scopes": {"payments:create": "Create"}}},
            }
        }
    },
    "paths": {
        "/payments": {
            "post": {
                "operationId": "createPayment",
                "security": [{"oauth": ["payments:create"]}],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "enum": ["pending"]}
                                },
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "enum": ["pending"],
                                        }
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/payments/{id}": {
            "get": {"operationId": "getPayment", "responses": {"200": {"description": "OK"}}},
            "delete": {
                "operationId": "voidPayment",
                "responses": {"204": {"description": "No Content"}},
            },
        },
        "/payments/{id}/capture": {
            "post": {
                "operationId": "capturePayment",
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}

CANDIDATE_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Payments API", "version": "2.0.0"},
    "paths": {
        "/payments": {
            "post": {
                "operationId": "createPayment",
                "security": [{"oauth": ["payments:write"]}],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "enum": ["pending", "captured"],
                                    },
                                    "amount": {"type": "integer"},
                                },
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "enum": ["pending", "captured"],
                                        },
                                        "id": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/payments/{id}": {
            "post": {
                "operationId": "voidPayment",
                "responses": {"204": {"description": "No Content"}},
            }
        },
        "/payments/{id}/captures": {
            "post": {
                "operationId": "capturePayment",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/refunds": {
            "post": {
                "operationId": "createRefund",
                "responses": {"202": {"description": "Accepted"}},
            }
        },
    },
}


class OpenAPIIntakeTests(unittest.TestCase):
    def test_openapi_candidate_import_records_structural_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "openapi.yaml"
            source.write_text(json.dumps(BASELINE_OPENAPI), encoding="utf-8")

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(source),
                    "--kind",
                    "openapi",
                    "--source-key",
                    "payments-api",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                    "--as-candidate",
                    "--json",
                ]
            )

            spec_document = load_data(
                root / payload["candidate_path"] / "spec-document.yml"
            )
            self.assertEqual(spec_document["kind"], "openapi")
            self.assertEqual(spec_document["api_version"], "3.1.0")
            self.assertEqual(spec_document["remote_version"], "1.0.0")
            contracts = {
                contract["operation_id"]: contract
                for contract in spec_document["api_contracts"]
            }
            create = contracts["createPayment"]
            self.assertEqual(create["method"], "POST")
            self.assertEqual(create["path"], "/payments")
            self.assertEqual(create["version"], "1.0.0")
            self.assertTrue(create["request_schema_hash"].startswith("sha256:"))
            self.assertTrue(create["response_schema_hashes"]["200"].startswith("sha256:"))
            self.assertEqual(create["auth_scopes"], ["oauth:payments:create"])
            self.assertEqual(create["enum_values"]["request.status"], ["pending"])

    def test_openapi_diff_reports_structural_contract_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "baseline.yaml"
            baseline.write_text(json.dumps(BASELINE_OPENAPI), encoding="utf-8")
            candidate = root / "candidate.yaml"
            candidate.write_text(json.dumps(CANDIDATE_OPENAPI), encoding="utf-8")
            baseline_payload = _import_openapi(root, baseline)
            baseline_spec = load_data(root / baseline_payload["candidate_path"] / "spec-document.yml")
            _seed_accepted_openapi_baseline(root, baseline_spec)
            _import_openapi(root, candidate)

            diff_payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "diff",
                    "SRC-0002",
                    "--baseline",
                    "accepted",
                    "--json",
                ]
            )

            self.assertEqual(diff_payload["schema"], "agentspec.intake.diff.v0")
            self.assertEqual(
                diff_payload["api_contract_summary"],
                {
                    "unchanged": 0,
                    "endpoint-added": 1,
                    "endpoint-removed": 1,
                    "path-changed": 1,
                    "method-changed": 1,
                    "request-schema-changed": 1,
                    "response-schema-changed": 1,
                    "auth-scope-changed": 1,
                    "enum-changed": 1,
                },
            )
            kinds = {change["kind"] for change in diff_payload["api_contract_changes"]}
            self.assertIn("endpoint-added", kinds)
            self.assertIn("endpoint-removed", kinds)
            self.assertIn("path-changed", kinds)
            self.assertIn("method-changed", kinds)
            self.assertIn("request-schema-changed", kinds)
            self.assertIn("response-schema-changed", kinds)
            self.assertIn("auth-scope-changed", kinds)
            self.assertIn("enum-changed", kinds)

            stdout = _run(
                [
                    "--root",
                    str(root),
                    "intake",
                    "diff",
                    "SRC-0002",
                    "--baseline",
                    "accepted",
                ]
            )
            self.assertIn("API Contract Changes:", stdout)
            self.assertIn("endpoint-added: 1", stdout)
            self.assertIn("request-schema-changed: 1", stdout)


def _import_openapi(root: Path, source: Path) -> dict[str, object]:
    return _run_json(
        [
            "--root",
            str(root),
            "intake",
            "import",
            str(source),
            "--kind",
            "openapi",
            "--source-key",
            "payments-api",
            "--classification",
            "internal",
            "--storage-mode",
            "committed",
            "--as-candidate",
            "--json",
        ]
    )


def _seed_accepted_openapi_baseline(root: Path, spec_document: dict[str, object]) -> None:
    write_data(
        root / "docs" / "source" / "sources.yml",
        [
            {
                "id": spec_document["snapshot_id"],
                "source_key": spec_document["source_key"],
                "kind": "openapi",
                "state": "accepted",
                "api_contracts": spec_document["api_contracts"],
            }
        ],
    )
    write_data(root / "docs" / "source" / "sections.yml", [])


def _run(args: list[str]) -> str:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = main(args)
    if rc != 0:
        raise AssertionError(f"command failed rc={rc}: {args}\n{stderr.getvalue()}")
    if stderr.getvalue():
        raise AssertionError(stderr.getvalue())
    return stdout.getvalue()


def _run_json(args: list[str]) -> dict[str, object]:
    return json.loads(_run(args))


if __name__ == "__main__":
    unittest.main()
