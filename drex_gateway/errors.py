"""Error hierarchy and provider error classification for Drex Decision Gateway."""
from __future__ import annotations

from enum import Enum
from typing import Any


class ProviderErrorKind(str, Enum):
    PROVIDER_AUTH = "PROVIDER_AUTH"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    UNKNOWN_PROVIDER_FAILURE = "UNKNOWN_PROVIDER_FAILURE"


class GatewayError(Exception):
    """Base error for all gateway exceptions."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderError(GatewayError):
    """Cleanly classified provider failures.

    Provider failures must never be converted into fake low-confidence decisions.
    """

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        status_code: int = 0,
        headers: dict[str, str] | None = None,
        retry_after_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(f"[{kind.value}] {message}", details=details)
        self.kind = kind
        self.status_code = status_code
        self.headers = headers or {}
        self.retry_after_seconds = retry_after_seconds


class ConfigurationError(GatewayError):
    """Invalid configuration or missing required credentials."""
    pass


class ValidationError(GatewayError):
    """Request payload, schema, or choice validation failure."""
    pass


class StorageError(GatewayError):
    """Database persistence or migration failure."""
    pass
