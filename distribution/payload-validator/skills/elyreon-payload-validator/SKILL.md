---
name: elyreon-payload-validator
description: Check JSON API payloads against a bounded JSON Schema and interpret structured pass or fail results using the free ELYREON validator.
---

Use https://elyreon-payload-validator.colt2822.workers.dev for deterministic JSON validation. Send sanitized JSON only. Payloads and schemas are not stored; usage metadata is retained for 30 days. No inference or payments.

1. POST `/trial` with `Content-Type: application/json` and `{"source":"skill_directory"}`. Save the returned token privately. For controlled evaluation include `"test":true`; this excludes the session from external adoption counts.
2. POST `/validate` with `Authorization: Bearer TOKEN`, JSON content type, and `{"schema":{"type":"object","properties":{"id":{"type":"integer"}},"required":["id"],"additionalProperties":false},"payload":{"id":42}}`.
3. Read `verdict`, `valid`, and `errors`. `FAIL` is a completed check with invalid data. `REJECTED` means the service could not check the input; fix the reported limit or unsupported schema. Preserve `receipt_id` as evidence. Do not treat structural validity as runtime or business correctness.

For MCP configure a Streamable HTTP server at `/mcp` with the same bearer header. Discover `validate_payload` via `tools/list`; arguments are `{schema,payload}`. MCP tool execution errors set `isError:true` and return structured `REJECTED` results.

Limits: 32 KiB total request including RPC envelope, depth 12, 2048 values, 128 schema nodes, one validation error, 20 calls/token/day. Supported draft 2020-12 keywords: `$schema`, title, description, type, properties, required, additionalProperties, items, scalar enum/const, numeric bounds, min/maxLength, min/maxItems, min/maxProperties. Boolean schemas accepted. All other keywords are rejected; no references, regex, formats, combinators, defaults or coercion. On 429 wait until the next quota window.

Example derived from the existing public Gateway request model: `/schemas/gateway-request.json`. It checks the documented choice-only subset; it does not call Drex or certify the entire Gateway API.
