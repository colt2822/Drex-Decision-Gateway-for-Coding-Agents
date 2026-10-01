"""Tests for MCP server protocol handling."""
import json
import pytest
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.mcp.server import McpServer


@pytest.mark.asyncio
async def test_mcp_initialize(gateway: DrexDecisionGateway):
    server = McpServer(gateway=gateway)
    resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    })
    assert resp is not None
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "drex-decision-gateway"


@pytest.mark.asyncio
async def test_mcp_tools_list(gateway: DrexDecisionGateway):
    server = McpServer(gateway=gateway)
    resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    assert resp is not None
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "drex_choose" in tool_names
    assert "drex_coding_preflight" in tool_names
    assert "drex_failure_triage" in tool_names


@pytest.mark.asyncio
async def test_mcp_tools_call(gateway: DrexDecisionGateway):
    server = McpServer(gateway=gateway)
    resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "drex_choose",
            "arguments": {
                "question": "Which verifier?",
                "choices": ["pytest", "npm_test"],
                "context": "Python backend",
            },
        },
    })
    assert resp is not None
    text_content = resp["result"]["content"][0]["text"]
    data = json.loads(text_content)
    assert data["selected"] in ["pytest", "npm_test"]
    assert "probabilities" in data
