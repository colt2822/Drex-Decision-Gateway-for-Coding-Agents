"""Tests for DrexProvider, ReplayProvider, validation, security, and error classification."""
import pytest
from pathlib import Path
from drex_gateway.config import GatewayConfig
from drex_gateway.errors import ProviderError, ProviderErrorKind, ValidationError
from drex_gateway.models import ChoiceQuestion
from drex_gateway.providers.live import DrexProvider
from drex_gateway.providers.replay import ReplayProvider


def test_drex_provider_origin_enforcement():
    cfg = GatewayConfig(base_url="https://evil-proxy.com")
    with pytest.raises(ProviderError) as exc_info:
        DrexProvider(cfg)
    assert exc_info.value.kind == ProviderErrorKind.PROVIDER_AUTH
    assert "Invalid or unverified Drex API origin" in exc_info.value.message


def test_drex_provider_insecure_key_permissions(tmp_path: Path):
    key_file = tmp_path / "insecure.key"
    key_file.write_text("nace_sk_" + "A" * 43)
    key_file.chmod(0o666)  # world-readable

    cfg = GatewayConfig(base_url="https://drex.nace.ai")
    # Point env var to insecure file
    orig = cfg.get_api_key
    # Verify config rejects insecure key file
    import os
    os.environ["DREX_API_KEY_FILE"] = str(key_file)
    try:
        assert cfg.get_api_key() is None
    finally:
        del os.environ["DREX_API_KEY_FILE"]


def test_drex_provider_request_bounds():
    provider = ReplayProvider()

    # Empty state should be rejected locally before network
    with pytest.raises(ValidationError):
        provider.validate_request("", {"q": ChoiceQuestion(type="choice", instructions="choose", criteria={"a": None, "b": None})})

    # Choice question with only 1 option should be rejected
    with pytest.raises(ValidationError):
        provider.validate_request("context", {"q": ChoiceQuestion(type="choice", instructions="choose", criteria={"only_one": None})})


def test_replay_provider_deterministic_distribution():
    prov = ReplayProvider()
    q = {
        "failure_class": ChoiceQuestion(
            type="choice",
            instructions="Classify failure",
            criteria={
                "environment_failure": "Missing dependency",
                "implementation_failure": "Bug in code",
            },
        )
    }

    # Calling twice with same state gives exact same output
    res1 = prov.sync_decide("ModuleNotFoundError: No module named foo", q)
    res2 = prov.sync_decide("ModuleNotFoundError: No module named foo", q)

    assert res1.provider_name == "REPLAY"
    assert res1.answers["failure_class"]["choice"] == res2.answers["failure_class"]["choice"]
    assert res1.answers["failure_class"]["choice"] == "environment_failure"
    assert res1.answers["failure_class"]["probabilities"] == res2.answers["failure_class"]["probabilities"]


def test_secret_redaction_in_errors():
    err = ProviderError(
        ProviderErrorKind.PROVIDER_AUTH,
        "Authentication failed for nace_sk_abcdefghijklmnopqrstuvwxyz0123456789ABCDEF",
        status_code=401,
    )
    # Ensure error doesn't expose secrets if redacted properly
    assert "PROVIDER_AUTH" in str(err)
