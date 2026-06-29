"""Model-backed continuation and quality review prompts and response parsing."""

from __future__ import annotations

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


MODEL_REVIEW_SCHEMA = "agentspec.model_review.verdict.v0"
QUALITY_REVIEW_SCHEMA = "agentspec.quality_review.verdict.v0"
PROFILE_DIAGNOSTICS_SCHEMA = "agentspec.agent_profile_diagnostics.v0"
ALLOWED_MODEL_DECISIONS = {"auto_continue", "pause_for_human", "halt", "complete"}
ALLOWED_QUALITY_DECISIONS = {"approve", "reject"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}


# ADR-0005 / R-143: deterministic severity rules for autonomous-mode
# pause classification. HIGH wins ties because mis-classifying a high
# concern as minor is the failure mode worth avoiding.
_HIGH_SEVERITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Security / credentials / compliance.
    re.compile(r"\b(?:secret|secrets|credential|credentials|token|tokens|api[\s-]*key|password|auth|authentication|authorization|permission(?:s)?|compliance)\b", re.IGNORECASE),
    # Product / scope / non-goal.
    re.compile(r"\b(?:product\s+position|scope[\s-]*expand(?:ing|sion|ed)?|expand\s+scope|non[\s-]*goal|deprecate|supersede)\b", re.IGNORECASE),
    # Architecture / design alternatives.
    re.compile(r"\b(?:architecture|architectural|fundamental\s+(?:design|change))\b", re.IGNORECASE),
    # ADR / requirement modification.
    re.compile(r"\b(?:modify|supersede|change)\s+(?:the\s+)?(?:adr|requirement|r-\d+)\b", re.IGNORECASE),
    re.compile(r"\bADR-\d+\b"),
    # Destructive operations.
    re.compile(r"\bforce[\s-]*push\b", re.IGNORECASE),
    re.compile(r"\breset\s+--hard\b", re.IGNORECASE),
    # `drop` followed (within ~3 words) by a destructive-noun.
    re.compile(r"\bdrop\b(?:\s+\S+){0,3}\s+(?:table|database|index|column|schema|users|all)\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+(?:all|everything|the\s+\w+)\b", re.IGNORECASE),
    re.compile(r"\b(?:wipe|destructive)\b", re.IGNORECASE),
)

_MINOR_SEVERITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Naming / style.
    re.compile(r"\b(?:rename|renaming|name\s+(?:should|for|this)|naming|style|format(?:ting)?|alias)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:should\s+(?:i|we)\s+)?(?:name|call)\b", re.IGNORECASE),
    # Default values.
    re.compile(r"\b(?:default\s+value|what\s+default|safe\s+default)\b", re.IGNORECASE),
    # Equivalent alternatives.
    re.compile(r"\b(?:either\s+way|both\s+work|equivalent|interchangeable|whichever)\b", re.IGNORECASE),
    # Routine elaboration.
    re.compile(r"\b(?:elaborate|expand\s+on|fill\s+in|flesh\s+out|verbose)\b", re.IGNORECASE),
)


def classify_severity(executor_output: str) -> str | None:
    """Classify a pause-style executor output as `minor`, `high`, or None.

    `high` always wins over `minor` so that a question mentioning both a
    naming choice and a security concern is treated as high. Returns
    None when neither rule set matches; the caller should fall back to
    a conservative default (T-028 path: open-question + halt).
    """
    if any(pattern.search(executor_output) for pattern in _HIGH_SEVERITY_PATTERNS):
        return "high"
    if any(pattern.search(executor_output) for pattern in _MINOR_SEVERITY_PATTERNS):
        return "minor"
    return None


def request_model_review(
    *,
    profile: dict[str, Any],
    executor_output: str,
    active_context_pack: str,
    deterministic_reason: str,
    test_status: str,
) -> dict[str, Any] | None:
    """Request and parse a continuation review, or return None if unavailable."""

    prompt = build_model_review_prompt(
        executor_output=executor_output,
        active_context_pack=active_context_pack,
        deterministic_reason=deterministic_reason,
        test_status=test_status,
    )
    raw = _raw_model_response(profile, prompt)
    if raw is None:
        return None
    return parse_model_review_response(raw)


def request_quality_review(
    *,
    profile: dict[str, Any],
    executor_output: str,
    test_status: str,
    deterministic_reason: str,
    acceptance_evidence: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Request and parse a quality review, or return None if unavailable."""

    prompt = build_quality_review_prompt(
        executor_output=executor_output,
        test_status=test_status,
        deterministic_reason=deterministic_reason,
        acceptance_evidence=acceptance_evidence,
    )
    raw = _raw_model_response(profile, prompt)
    if raw is None:
        return None
    return parse_quality_review_response(raw)


def build_model_review_prompt(
    *,
    executor_output: str,
    active_context_pack: str,
    deterministic_reason: str,
    test_status: str,
) -> str:
    """Build the bounded JSON-only continuation reviewer prompt."""

    return "\n".join(
        [
            "You are an AgentSpec continuation reviewer.",
            "Return only JSON with this schema:",
            "{",
            f'  "schema": "{MODEL_REVIEW_SCHEMA}",',
            '  "decision": "auto_continue|pause_for_human|halt|complete",',
            '  "confidence": "low|medium|high",',
            '  "reason": "short reason",',
            '  "message_to_executor": "short instruction or null"',
            "}",
            "",
            "Rules:",
            "- Do not expand scope beyond the active context pack.",
            "- Prefer auto_continue only for low-risk continuation within the current pack.",
            "- Use pause_for_human for ambiguity, missing information, or task choice.",
            "- Use halt for unsafe or policy-sensitive behavior.",
            "- Use complete only when the executor explicitly reports completion and verification passed.",
            "",
            f"Active context pack: {active_context_pack}",
            f"Deterministic reviewer reason: {deterministic_reason}",
            f"Test status: {test_status}",
            "Executor output:",
            executor_output[:4000],
        ]
    )


def build_quality_review_prompt(
    *,
    executor_output: str,
    test_status: str,
    deterministic_reason: str,
    acceptance_evidence: dict[str, Any] | None = None,
) -> str:
    """Build the bounded JSON-only quality reviewer prompt."""

    evidence_note = (
        json.dumps(acceptance_evidence, sort_keys=True)[:2000]
        if acceptance_evidence is not None
        else "null"
    )
    return "\n".join(
        [
            "You are an AgentSpec test/eval reviewer.",
            "Return only JSON with this schema:",
            "{",
            f'  "schema": "{QUALITY_REVIEW_SCHEMA}",',
            '  "decision": "approve|reject",',
            '  "confidence": "low|medium|high",',
            '  "reason": "short reason"',
            "}",
            "",
            "Rules:",
            "- Approve only when verification passed and the executor output or evidence supports the acceptance criteria.",
            "- Reject when tests failed, evidence is missing, scope is unclear, or the output does not support task completion.",
            "- For app/UI tasks, expect browser-oriented evidence when the runner reports it.",
            "",
            f"Deterministic quality result: {deterministic_reason}",
            f"Test status: {test_status}",
            f"Acceptance evidence: {evidence_note}",
            "Executor output:",
            executor_output[:4000],
        ]
    )


def parse_model_review_response(raw: str) -> dict[str, Any]:
    """Validate and normalize a continuation reviewer JSON response.

    Raises:
        ValueError: If the response is not valid reviewer JSON.
    """

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Model reviewer response must be JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Model reviewer response must be a JSON object.")
    schema = payload.get("schema")
    if schema != MODEL_REVIEW_SCHEMA:
        raise ValueError(f"Model reviewer schema must be {MODEL_REVIEW_SCHEMA}.")
    decision = payload.get("decision")
    if decision not in ALLOWED_MODEL_DECISIONS:
        raise ValueError(f"Model reviewer decision must be one of {sorted(ALLOWED_MODEL_DECISIONS)}.")
    confidence = payload.get("confidence", "medium")
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "medium"
    message = payload.get("message_to_executor")
    if message is not None and not isinstance(message, str):
        message = None
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "Model reviewer returned a structured verdict."

    return {
        "schema": schema,
        "decision": decision,
        "confidence": confidence,
        "reason": reason.strip(),
        "message_to_executor": message.strip() if isinstance(message, str) and message.strip() else None,
    }


def parse_quality_review_response(raw: str) -> dict[str, Any]:
    """Validate and normalize a quality reviewer JSON response.

    Raises:
        ValueError: If the response is not valid quality-review JSON.
    """

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Quality reviewer response must be JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Quality reviewer response must be a JSON object.")
    schema = payload.get("schema")
    if schema != QUALITY_REVIEW_SCHEMA:
        raise ValueError(f"Quality reviewer schema must be {QUALITY_REVIEW_SCHEMA}.")
    decision = payload.get("decision")
    if decision not in ALLOWED_QUALITY_DECISIONS:
        raise ValueError(f"Quality reviewer decision must be one of {sorted(ALLOWED_QUALITY_DECISIONS)}.")
    confidence = payload.get("confidence", "medium")
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "medium"
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "Quality reviewer returned a structured verdict."

    return {
        "schema": schema,
        "decision": decision,
        "confidence": confidence,
        "reason": reason.strip(),
    }


def _raw_model_response(profile: dict[str, Any], prompt: str) -> str | None:
    adapter = profile.get("adapter")
    if adapter == "static":
        response = profile.get("response")
        return response if isinstance(response, str) else None
    if adapter == "codex":
        return _litellm_chat_completion(profile, prompt)
    return None


def build_agent_profile_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    """Return non-secret model/profile health for AgentSpec control-plane use."""

    profiles = config.get("agent_profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    runs = config.get("supervised_runs")
    if not isinstance(runs, dict):
        runs = {}
    bindings = {
        "executor": str(runs.get("executor_profile") or "main_executor"),
        "continuation_reviewer": str(runs.get("continuation_reviewer_profile") or "continuation_reviewer"),
        "quality_reviewer": str(runs.get("quality_reviewer_profile") or "quality_reviewer"),
    }
    roles_by_profile: dict[str, list[str]] = {}
    for role, profile_name in bindings.items():
        roles_by_profile.setdefault(profile_name, []).append(role)

    profile_payload = {
        name: _profile_diagnostic(name, profile, roles_by_profile.get(name, []))
        for name, profile in sorted(profiles.items())
        if isinstance(profile, dict)
    }
    for profile_name, roles in roles_by_profile.items():
        if profile_name not in profile_payload:
            profile_payload[profile_name] = _missing_profile_diagnostic(profile_name, roles)

    warnings = [
        {
            "profile": name,
            "message": warning,
        }
        for name, diagnostic in profile_payload.items()
        for warning in diagnostic.get("warnings", [])
    ]
    return {
        "schema": PROFILE_DIAGNOSTICS_SCHEMA,
        "status": "warning" if warnings else "ready",
        "bindings": bindings,
        "profiles": profile_payload,
        "warnings": warnings,
    }


def _profile_diagnostic(name: str, profile: dict[str, Any], roles: list[str]) -> dict[str, Any]:
    adapter = profile.get("adapter")
    configured_model = profile.get("model")
    base = {
        "name": name,
        "roles": sorted(roles),
        "adapter": adapter,
        "configured_model": configured_model if isinstance(configured_model, str) else None,
        "resolved_model": None,
        "model_source": "missing",
        "config_source": profile.get("config_source") if isinstance(profile.get("config_source"), str) else None,
        "credential_source": profile.get("credential_source") if isinstance(profile.get("credential_source"), str) else None,
        "config_source_status": "not_applicable",
        "credential_status": "not_applicable",
        "usable_for_model_review": False,
        "status": "unsupported_adapter",
        "warnings": [],
    }

    if adapter == "current-host":
        return {
            **base,
            "resolved_model": configured_model if isinstance(configured_model, str) else None,
            "model_source": "profile" if isinstance(configured_model, str) and configured_model.strip() else "host-default",
            "status": "deterministic_only",
            "warnings": [
                "current-host profiles label the interactive executor; AgentSpec does not invoke them as model reviewers."
            ]
            if roles and roles != ["executor"]
            else [],
        }
    if adapter == "static":
        has_response = isinstance(profile.get("response"), str)
        return {
            **base,
            "resolved_model": configured_model if isinstance(configured_model, str) else None,
            "model_source": "profile" if isinstance(configured_model, str) and configured_model.strip() else "missing",
            "credential_status": "not_required",
            "usable_for_model_review": has_response,
            "status": "ready" if has_response else "unavailable",
            "warnings": [] if has_response else ["static reviewer profile has no response payload."],
        }
    if adapter == "codex":
        return _codex_profile_diagnostic(name, profile, roles, base)

    return {
        **base,
        "warnings": [f"Unsupported reviewer profile adapter: {adapter!r}."],
    }


def _missing_profile_diagnostic(name: str, roles: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "roles": sorted(roles),
        "adapter": None,
        "configured_model": None,
        "resolved_model": None,
        "model_source": "missing",
        "config_source": None,
        "credential_source": None,
        "config_source_status": "missing",
        "credential_status": "missing",
        "usable_for_model_review": False,
        "status": "missing",
        "warnings": [f"Active profile binding references missing agent profile {name!r}."],
    }


def _codex_profile_diagnostic(
    name: str,
    profile: dict[str, Any],
    roles: list[str],
    base: dict[str, Any],
) -> dict[str, Any]:
    configured_model = profile.get("model")
    settings = _resolve_chat_settings(profile)
    resolved_model = settings.get("model")
    base_url = settings.get("base_url")
    config_source = profile.get("config_source")
    config_status = "not_configured"
    if config_source == "codex-config":
        config_status = "found" if _load_codex_config() else "missing"
    credential_status = _credential_status(profile)
    has_endpoint = isinstance(base_url, str) and bool(base_url.strip())
    has_model = isinstance(resolved_model, str) and bool(resolved_model.strip())
    has_token = credential_status in {"profile", "env", "codex-auth"}
    warnings: list[str] = []
    if not has_endpoint:
        warnings.append("Codex reviewer profile cannot resolve a LiteLLM/OpenAI-compatible base_url.")
    if not has_model:
        warnings.append("Codex reviewer profile cannot resolve a model id.")
    if not has_token:
        warnings.append("Codex reviewer profile cannot resolve credentials from profile, env, or codex-auth.")

    explicit_model = isinstance(configured_model, str) and bool(configured_model.strip())
    model_source = "profile" if explicit_model else "codex-config" if has_model else "missing"
    return {
        **base,
        "roles": sorted(roles),
        "configured_model": configured_model if explicit_model else None,
        "resolved_model": resolved_model if isinstance(resolved_model, str) and resolved_model.strip() else None,
        "model_source": model_source,
        "config_source_status": config_status,
        "credential_status": credential_status,
        "usable_for_model_review": has_endpoint and has_model and has_token,
        "status": "ready" if has_endpoint and has_model and has_token else "unavailable",
        "warnings": warnings,
    }


def _credential_status(profile: dict[str, Any]) -> str:
    token = profile.get("api_key")
    if isinstance(token, str) and token.strip():
        return "profile"
    if isinstance(os.environ.get("AGENTSPEC_LITELLM_API_KEY"), str) and os.environ.get("AGENTSPEC_LITELLM_API_KEY", "").strip():
        return "env"
    if profile.get("credential_source") != "codex-auth":
        return "not_configured"
    auth_path = Path.home() / ".codex" / "auth.json"
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "missing"
    token = auth.get("OPENAI_API_KEY")
    return "codex-auth" if isinstance(token, str) and token.strip() else "missing"


def _litellm_chat_completion(profile: dict[str, Any], prompt: str) -> str | None:
    settings = _resolve_chat_settings(profile)
    base_url = settings.get("base_url")
    model = settings.get("model")
    if not isinstance(base_url, str) or not base_url.strip() or not isinstance(model, str) or not model.strip():
        return None

    token = _resolve_token(profile)
    if token is None:
        return None

    url = _chat_completions_url(base_url)
    request_body = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON. Do not include markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=request_body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "client": "codex-cli",
            "client-version": "0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return content if isinstance(content, str) else None


def _resolve_chat_settings(profile: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "base_url": profile.get("base_url") or os.environ.get("AGENTSPEC_LITELLM_BASE_URL"),
        "model": profile.get("model"),
    }
    if profile.get("config_source") != "codex-config":
        return settings

    codex = _load_codex_config()
    provider_name = profile.get("provider") or profile.get("model_provider") or codex.get("model_provider")
    provider = _codex_provider(codex, provider_name)
    settings["base_url"] = settings["base_url"] or provider.get("base_url") or codex.get("base_url")
    settings["model"] = settings["model"] or codex.get("model")
    return settings


def _load_codex_config() -> dict[str, Any]:
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _codex_provider(codex_config: dict[str, Any], provider_name: Any) -> dict[str, Any]:
    providers = codex_config.get("model_providers")
    if not isinstance(providers, dict) or not isinstance(provider_name, str):
        return {}
    provider = providers.get(provider_name)
    return provider if isinstance(provider, dict) else {}


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return normalized + "/chat/completions"


def _resolve_token(profile: dict[str, Any]) -> str | None:
    token = profile.get("api_key") or os.environ.get("AGENTSPEC_LITELLM_API_KEY")
    if isinstance(token, str) and token.strip():
        return token.strip()
    if profile.get("credential_source") != "codex-auth":
        return None

    auth_path = Path.home() / ".codex" / "auth.json"
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = auth.get("OPENAI_API_KEY")
    return token.strip() if isinstance(token, str) and token.strip() else None
