from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .io import load_data


def default_agent_profiles() -> dict[str, dict[str, Any]]:
    """Return portable defaults for agent/model profile configuration."""

    return {
        "main_executor": {
            "adapter": "current-host",
            "model": "host-default",
        },
        "continuation_reviewer": {
            "adapter": "codex",
            "credential_source": "codex-auth",
            "config_source": "codex-config",
            "model": None,
            "reasoning": "low",
        },
        "quality_reviewer": {
            "adapter": "codex",
            "credential_source": "codex-auth",
            "config_source": "codex-config",
            "model": None,
            "reasoning": "high",
        },
    }


def default_supervised_run_config() -> dict[str, Any]:
    return {
        "executor_profile": "main_executor",
        "continuation_reviewer_profile": "continuation_reviewer",
        "quality_reviewer_profile": "quality_reviewer",
        "reviewer_mode": "deterministic",
        "max_iterations": {
            "implementation": 3,
            "spike": 2,
            "spec": 2,
            "review": 2,
        },
    }


def default_autonomous_mode_config() -> dict[str, Any]:
    """Soft-limit defaults for autonomous mode per ADR-0004.

    Hard limits are encoded in `agentspec.policy` and cannot be relaxed
    by config. The values here govern how findings are routed and how
    eagerly the loop bails out.
    """
    return {
        "findings_dir": "docs/discovery/open-questions.yml",
        "allow_remote_push": False,
        "max_consecutive_blocks": 3,
    }


def default_runtime_config() -> dict[str, Any]:
    return {
        "agent_profiles": default_agent_profiles(),
        "supervised_runs": default_supervised_run_config(),
        "autonomous_mode": default_autonomous_mode_config(),
    }


def load_project_config(root: Path) -> dict[str, Any]:
    config = load_data(root / ".agentspec" / "config.yml", {})
    if not isinstance(config, dict):
        raise ValueError(".agentspec/config.yml must contain a JSON/YAML object.")
    return config


def merged_runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(config)
    defaults = default_runtime_config()
    profiles = merged.setdefault("agent_profiles", {})
    for name, profile in defaults["agent_profiles"].items():
        profiles.setdefault(name, profile)
    supervised = merged.setdefault("supervised_runs", {})
    for key, value in defaults["supervised_runs"].items():
        supervised.setdefault(key, value)
    autonomous = merged.setdefault("autonomous_mode", {})
    for key, value in defaults["autonomous_mode"].items():
        autonomous.setdefault(key, value)
    return merged


def resolve_agent_profile(config: dict[str, Any], profile_name: str) -> dict[str, Any]:
    merged = merged_runtime_config(config)
    profiles = merged.get("agent_profiles", {})
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise ValueError(f"Agent profile not found: {profile_name}")
    return profile
