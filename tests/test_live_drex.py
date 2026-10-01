"""Bounded live validation for production Drex API at https://drex.nace.ai.

Runs only when authorized credentials exist in the environment or standard secure key file.
Skips safely otherwise without failing CI or offline runs.
"""
import pytest
from drex_gateway.config import GatewayConfig
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import ChoiceQuestion, NoulQuestion, BatchDecisionRequest
from drex_gateway.providers.live import DrexProvider


def live_credentials_available() -> bool:
    cfg = GatewayConfig.from_env()
    return cfg.has_live_credentials()


@pytest.mark.skipif(not live_credentials_available(), reason="Live Drex API credentials not available")
@pytest.mark.asyncio
async def test_live_drex_connection_and_models(tmp_db_path: str):
    cfg = GatewayConfig(db_path=tmp_db_path, force_provider="LIVE")
    provider = DrexProvider(cfg)

    # 1. Non-billed GET /v1/models
    models = await provider.list_models()
    assert isinstance(models, list)
    model_names = [m["name"] for m in models]
    assert "drex-latest" in model_names or "drex-v1.5" in model_names


@pytest.mark.skipif(not live_credentials_available(), reason="Live Drex API credentials not available")
@pytest.mark.asyncio
async def test_live_drex_decide_and_telemetry(tmp_db_path: str):
    cfg = GatewayConfig(db_path=tmp_db_path, force_provider="LIVE")
    gateway = DrexDecisionGateway(config=cfg)

    assert gateway.provider_mode == "LIVE"

    # Single bounded live choose call
    res = await gateway.choose(
        question="Which subsystem owns this defect?",
        choices={"auth": "Authentication & JWT tokens", "billing": "Stripe & subscription logic"},
        context="Defect report: Invalid signature on JWT bearer token in Authorization header",
        decision_type="REPOSITORY_AREA",
    )

    assert res.provider == "Drex"
    assert res.selected == "auth"
    assert res.confidence >= 0.70
    assert res.latency_ms > 0.0
    assert res.provider_latency_ms is not None  # evaluation_time_ms from Drex API
    assert res.input_tokens is not None
    assert res.output_tokens is not None

    # Verify decision is durably persisted in DB with full probability fidelity
    loaded = gateway.db.get_decision(res.decision_id)
    assert loaded is not None
    assert loaded.selected == "auth"
    assert loaded.provider == "Drex"
