"""Model Context Protocol (MCP) server for Drex Decision Gateway.

Exposes Drex decision tools to MCP-compatible coding agents (Cursor, Claude Code, Windsurf).
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import ChoiceQuestion, NoulQuestion, ScoreQuestion
from drex_gateway.workflows.failure_triage import FailureTriageWorkflow
from drex_gateway.workflows.patch_triage import PatchTriageWorkflow
from drex_gateway.workflows.preflight import PreflightWorkflow

TOOLS_DEFINITIONS = [
    {
        "name": "drex_choose",
        "description": "Make a fast, calibrated structured choice between 2 to 64 discrete options using Drex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The decision question"},
                "choices": {"type": "array", "items": {"type": "string"}, "description": "List of discrete choice options"},
                "context": {"type": "string", "description": "Context, diff, or error output"},
                "decision_type": {"type": "string", "description": "Optional decision type identifier"},
            },
            "required": ["question", "choices", "context"],
        },
    },
    {
        "name": "drex_yes_no",
        "description": "Make a binary YES/NO decision with calibrated probability using Drex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to answer YES or NO"},
                "context": {"type": "string", "description": "Context or code snippet"},
                "decision_type": {"type": "string", "description": "Optional decision type identifier"},
            },
            "required": ["question", "context"],
        },
    },
    {
        "name": "drex_rate",
        "description": "Rate or score risk, complexity, or quality across ordered levels using Drex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Rating question"},
                "criteria": {"type": "array", "items": {"type": "string"}, "description": "Ordered levels (e.g. ['low', 'medium', 'high'])"},
                "context": {"type": "string", "description": "Context or code snippet"},
            },
            "required": ["question", "criteria", "context"],
        },
    },
    {
        "name": "drex_coding_preflight",
        "description": "Preflight an engineering issue before expensive LLM planning: determines complexity, subsystem, target verifier, and architecture risk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "The problem description or issue"},
                "repo_summary": {"type": "string", "description": "Repository overview or file tree"},
            },
            "required": ["task_description"],
        },
    },
    {
        "name": "drex_patch_triage",
        "description": "Triage a candidate patch after generation: evaluates scope, completeness, risk, missing tests, and review readiness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_objective": {"type": "string", "description": "Original goal"},
                "patch_diff": {"type": "string", "description": "Generated diff"},
                "verifier_evidence": {"type": "string", "description": "Test or build output"},
            },
            "required": ["task_objective", "patch_diff", "verifier_evidence"],
        },
    },
    {
        "name": "drex_failure_triage",
        "description": "Diagnose test or toolchain failure to identify root cause and prevent wasting coding agent tokens on environment errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "Task objective"},
                "changed_files": {"type": "array", "items": {"type": "string"}},
                "verifier_command": {"type": "string", "description": "Test command that failed"},
                "exit_code": {"type": "integer"},
                "stdout_stderr": {"type": "string", "description": "Compiler or test error traceback"},
            },
            "required": ["objective", "changed_files", "verifier_command", "exit_code", "stdout_stderr"],
        },
    },
]


class McpServer:
    """Standard JSON-RPC 2.0 stdio server implementing the Model Context Protocol."""

    def __init__(self, gateway: DrexDecisionGateway | None = None):
        self.gateway = gateway or DrexDecisionGateway()
        self.preflight_wf = PreflightWorkflow(self.gateway)
        self.patch_triage_wf = PatchTriageWorkflow(self.gateway)
        self.failure_triage_wf = FailureTriageWorkflow(self.gateway)

    async def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "drex-decision-gateway", "version": "0.1.0"},
                },
            }

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS_DEFINITIONS},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                content = await self._execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(content, indent=2)}]},
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": f"Tool execution failed: {type(exc).__name__}: {exc}"}],
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method {method} not found"},
            }

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "drex_choose":
            res = await self.gateway.choose(
                question=args["question"],
                choices=args["choices"],
                context=args["context"],
                decision_type=args.get("decision_type", "choose"),
            )
            return res.model_dump()

        elif name == "drex_yes_no":
            res = await self.gateway.yes_no(
                question=args["question"],
                context=args["context"],
                decision_type=args.get("decision_type", "yes_no"),
            )
            return res.model_dump()

        elif name == "drex_rate":
            res = await self.gateway.rate(
                question=args["question"],
                criteria=args["criteria"],
                context=args["context"],
            )
            return res.model_dump()

        elif name == "drex_coding_preflight":
            res = await self.preflight_wf.run(
                task_description=args["task_description"],
                repo_summary=args.get("repo_summary", ""),
            )
            return res.model_dump()

        elif name == "drex_patch_triage":
            res = await self.patch_triage_wf.run(
                task_objective=args["task_objective"],
                patch_diff=args["patch_diff"],
                verifier_evidence=args["verifier_evidence"],
            )
            return res.model_dump()

        elif name == "drex_failure_triage":
            res = await self.failure_triage_wf.run(
                objective=args["objective"],
                changed_files=args["changed_files"],
                verifier_command=args["verifier_command"],
                exit_code=int(args["exit_code"]),
                stdout_stderr=args["stdout_stderr"],
            )
            return res.model_dump()

        else:
            raise ValueError(f"Unknown tool: {name}")

    async def run_stdio(self):
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            try:
                req = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            resp = await self.handle_request(req)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def run_mcp_cli():
    server = McpServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    run_mcp_cli()
