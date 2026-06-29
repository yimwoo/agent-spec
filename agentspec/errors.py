"""Structured AgentSpec domain errors for CLI and runner boundaries."""

from __future__ import annotations

from typing import Any


ERROR_SCHEMA = "agentspec.error.v1"


class AgentSpecError(Exception):
    """Base class for AgentSpec domain errors that cross control boundaries."""

    code = "ASPEC_INTERNAL"
    layer = "python"
    retryable = False
    severity = "error"

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        recovery_command: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        layer: str | None = None,
        severity: str | None = None,
        type_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.recovery_command = recovery_command
        self.details = details or {}
        self.type_name = type_name
        self._retryable = self.retryable if retryable is None else retryable
        self._layer = self.layer if layer is None else layer
        self._severity = self.severity if severity is None else severity

    @property
    def effective_retryable(self) -> bool:
        """Return the instance-level retryability decision."""

        return self._retryable

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error into the stable public error envelope."""

        payload: dict[str, Any] = {
            "schema": ERROR_SCHEMA,
            "code": self.code,
            "message": str(self),
            "layer": self._layer,
            "retryable": self._retryable,
            "severity": self._severity,
        }
        if self.operation is not None:
            payload["operation"] = self.operation
        if self.recovery_command is not None:
            payload["recovery_command"] = self.recovery_command
        if self.details:
            payload["details"] = self.details
        return payload


class AgentSpecValidationError(AgentSpecError):
    """Raised when caller input or lifecycle state fails validation."""

    code = "ASPEC_VALIDATION"
    layer = "control_plane"


class RunStateNotFoundError(AgentSpecError):
    """Raised when a requested supervised-run state cannot be found."""

    code = "ASPEC_STATE_NOT_FOUND"
    layer = "control_plane"


class AgentSpecIOPermissionError(AgentSpecError):
    """Raised when AgentSpec cannot read or write a required path."""

    code = "ASPEC_IO_PERMISSION"
    layer = "control_plane"


class RunnerResultInvalidError(AgentSpecValidationError):
    """Raised when an external runner result violates its contract."""

    code = "ASPEC_RUNNER_RESULT_INVALID"
    layer = "execution"


class RunnerTimeoutError(AgentSpecError):
    """Raised for retryable external runner timeouts."""

    code = "ASPEC_RUNNER_TIMEOUT"
    layer = "execution"
    retryable = True


class RunnerStartFailedError(AgentSpecError):
    """Raised when an external runner process cannot be started."""

    code = "ASPEC_RUNNER_START_FAILED"
    layer = "execution"
