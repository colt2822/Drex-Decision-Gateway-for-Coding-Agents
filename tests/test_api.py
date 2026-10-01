"""Tests for FastAPI HTTP API endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient
from drex_gateway.api.app import create_app
from drex_gateway.gateway import DrexDecisionGateway


@pytest.mark.asyncio
async def test_api_endpoints(gateway: DrexDecisionGateway):
    app = create_app(gateway=gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Healthz
        r = await client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        # 2. Readyz
        r = await client.get("/readyz")
        assert r.status_code == 200

        # 3. Models
        r = await client.get("/v1/models")
        assert r.status_code == 200
        assert len(r.json()["models"]) > 0

        # 4. Choose endpoint
        r = await client.post(
            "/v1/decide/choose",
            json={
                "question": "Which verifier?",
                "choices": ["pytest", "npm_test"],
                "context": "Python repo",
                "decision_type": "VERIFIER_SELECTION",
            },
        )
        assert r.status_code == 200
        dec = r.json()
        assert dec["selected"] in ["pytest", "npm_test"]
        assert "decision_id" in dec
        dec_id = dec["decision_id"]

        # 5. Get decision by ID
        r = await client.get(f"/v1/decisions/{dec_id}")
        assert r.status_code == 200
        assert r.json()["decision_id"] == dec_id

        # 6. Record outcome
        r = await client.post(
            f"/v1/decisions/{dec_id}/outcome",
            json={"outcome": "VERIFIER_PASS", "success": True},
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "VERIFIER_PASS"

        # 7. Stats
        r = await client.get("/v1/stats")
        assert r.status_code == 200
        assert r.json()["decisions_total"] >= 1

        # 8. Metrics (Prometheus)
        r = await client.get("/metrics")
        assert r.status_code == 200
        assert "drex_decisions_total" in r.text
