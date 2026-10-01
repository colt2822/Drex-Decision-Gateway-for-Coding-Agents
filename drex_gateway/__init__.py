"""Drex Decision Gateway: High-throughput decision layer for coding agents powered by Drex."""
from drex_gateway.config import GatewayConfig
from drex_gateway.errors import GatewayError, ProviderError, ProviderErrorKind, ValidationError
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import (
    BatchDecisionRequest,
    BatchDecisionResult,
    DecisionResult,
    Disposition,
    OutcomeRecord,
    OutcomeType,
    ProviderMode,
    TraceSummary,
)
from drex_gateway.sdk.client import DrexGateway

__all__ = [
    "DrexGateway",
    "DrexDecisionGateway",
    "GatewayConfig",
    "DecisionResult",
    "BatchDecisionRequest",
    "BatchDecisionResult",
    "Disposition",
    "ProviderMode",
    "OutcomeType",
    "OutcomeRecord",
    "TraceSummary",
    "GatewayError",
    "ProviderError",
    "ProviderErrorKind",
    "ValidationError",
]
