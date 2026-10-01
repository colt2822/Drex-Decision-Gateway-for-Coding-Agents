"""Pytest fixtures for Drex Decision Gateway test suite."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from drex_gateway.config import GatewayConfig
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.providers.replay import ReplayProvider
from drex_gateway.storage.db import Database


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_gateway.db")


@pytest.fixture
def test_db(tmp_db_path: str) -> Database:
    db = Database(tmp_db_path)
    yield db
    db.close()


@pytest.fixture
def replay_provider() -> ReplayProvider:
    return ReplayProvider(latency_sim_ms=2.0)


@pytest.fixture
def gateway(tmp_db_path: str, replay_provider: ReplayProvider) -> DrexDecisionGateway:
    cfg = GatewayConfig(
        db_path=tmp_db_path,
        force_provider="REPLAY",
    )
    gw = DrexDecisionGateway(config=cfg, provider=replay_provider)
    return gw
