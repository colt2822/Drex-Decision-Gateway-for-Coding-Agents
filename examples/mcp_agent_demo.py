#!/usr/bin/env python3
"""Model Context Protocol (MCP) Server Example.

Demonstrates using Drex Decision Gateway as an MCP server for coding agents.
MCP clients (such as Claude Desktop, Cursor, or custom agent runtimes) interact
with Drex via standard JSON-RPC 2.0 tools.

Exposed MCP Tools:
- drex_choose: Execute discrete multi-choice decision
- drex_yes_no: Execute binary decision
- drex_coding_preflight: Scope tasks and configure bounds before generation
- drex_failure_triage: Classify verifier failure root cause
- drex_record_outcome: Attach downstream ground-truth outcome
"""
import asyncio
import json
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.mcp.server import McpServer


async def main():
    print("=== Drex Decision Gateway: MCP Server Demo ===\n")

    gateway = DrexDecisionGateway()
    mcp_server = McpServer(gateway)

    # 1. MCP initialize handshake
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "ExampleCodingAgent", "version": "1.0"},
        },
    }
    init_res = await mcp_server.handle_request(init_req)
    print(f"[1] MCP Initialize Response: server={init_res['result']['serverInfo']['name']}")

    # 2. List tools available to the agent
    tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    tools_res = await mcp_server.handle_request(tools_req)
    tools = tools_res["result"]["tools"]
    print(f"\n[2] Available MCP Tools ({len(tools)}):")
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:70]}...")

    # 3. Call tool: drex_choose
    print("\n[3] Calling 'drex_choose' via MCP...")
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "drex_choose",
            "arguments": {
                "question": "Which test runner applies to this Python repository?",
                "choices": ["pytest", "npm_test", "cargo_test"],
                "context": "Python FastAPI repository with pytest.ini and tests/ directory.",
            },
        },
    }
    call_res = await mcp_server.handle_request(call_req)
    result_data = json.loads(call_res["result"]["content"][0]["text"])

    print(f"MCP Tool Result:")
    print(f"  Selected:    {result_data['selected']}")
    print(f"  Confidence:  {result_data['confidence']:.2%}")
    print(f"  Disposition: {result_data['disposition']}")
    print(f"  Probabilities: {result_data['probabilities']}")


if __name__ == "__main__":
    asyncio.run(main())
