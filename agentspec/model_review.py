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
ALLOWED_MODEL_DECISIONS = {"auto_continue", "pause_for_human", "halt", "complete"}
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


def build_model_review_prompt(
    *,
    executor_output: str,
    active_context_pack: str,
    deterministic_reason: str,
    test_status: str,
) -> str:
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


def parse_model_review_response(raw: str) -> dict[str, Any]:
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


def _raw_model_response(profile: dict[str, Any], prompt: str) -> str | None:
    adapter = profile.get("adapter")
    if adapter == "static":
        response = profile.get("response")
        return response if isinstance(response, str) else None
    if adapter == "codex":
        return _litellm_chat_completion(profile, prompt)
    return None


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
