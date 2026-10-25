# ELYREON Payload Validator

Small, deterministic first-party distribution test in the existing public Decision Gateway repository. This isolated Worker validates JSON against an explicitly bounded JSON Schema 2020-12 subset. It does not call Nace.AI, expose Drex inference, execute uploaded code, or accept payments.

Endpoint: https://elyreon-payload-validator.colt2822.workers.dev

MCP: append `/mcp`. Get a free bearer token at `POST /trial` with JSON `{"source":"github"}`; send `{"test":true,"source":"github"}` for controlled evaluations. Configure the bearer header in any Streamable HTTP MCP client, discover `validate_payload`, and call with `{schema,payload}`. Direct HTTP uses `POST /validate` with the same token and input.

Install the [Agent Skill](skills/elyreon-payload-validator/SKILL.md) in the client's skill directory. Portable git install:

```sh
git clone --depth 1 https://github.com/colt2822/Drex-Decision-Gateway-for-Coding-Agents.git
mkdir -p ~/.agents/skills/elyreon-payload-validator
cp Drex-Decision-Gateway-for-Coding-Agents/distribution/payload-validator/skills/elyreon-payload-validator/SKILL.md ~/.agents/skills/elyreon-payload-validator/
```

Limits: 32 KiB request, depth 12, 2048 values, 128 schema nodes, 3-second body timeout; one validation error. Free quota: 20 invocations/token/day, 1000 invocations/service/day, 100 enrollments/service/day, 5 enrollments/IP/hour; edge limit 30 requests/IP/minute/location. Schema references, regex, formats and combinators are rejected. Supported keywords are documented in the skill. Validation does not certify runtime behavior. Malformed/unsupported input returns `REJECTED`; invalid data returns completed `FAIL`.

Deployment has a separate Worker and D1 database, no custom routes or other production bindings. Worker stores no input bodies, schemas or raw IPs. Token hashes and usage metadata are retained 30 days. Source is client-claimed; tokens are not verified customers. PHOENIX monitoring uses its existing controller timer and CRM; all five seats remain intact. Controlled tests are marked synthetic. No outbound sender or payment system is invoked. Provider inference cost is zero; hosting costs require billing evidence.

`server.json` is Official MCP Registry metadata. `/.well-known/ai-catalog.json` is a self-hosted catalog, not proof of a third-party listing. `/x402-bazaar.json` is inactive draft metadata with no accepted payment methods; it is not a paid Bazaar listing.

Validation: `npm ci`, `npm test`, `python3 tests/reference_check.py`, `python3 -m unittest discover -s tests -p 'test_monitor.py'`, `npm run dry-run`. Local HTTP acceptance uses `wrangler d1 execute elyreon-payload-validator --local --file migration.sql`, then `wrangler dev --port 18741 --var PRIVACY_SALT:local-only --var SYNC_TOKEN:local-only`, then `python3 tests/http_check.py`.

Deploy with `npm run deploy` only to the named isolated Worker, preserving secrets. Roll back using `wrangler rollback VERSION_ID`; for the first deployment, disable only this Worker's workers.dev endpoint. Never change existing website routes. Secrets SYNC_TOKEN, TEST_TOKEN and PRIVACY_SALT are kept outside git. Registration authentication files must remain outside git.

The Official MCP Registry listing is `co.com.elyraon/payload-validator` version `1.0.0`. [Registry readback](evidence/registry-readback.json), [clean public installation and MCP acceptance](evidence/clean-client.json), and [receipt attribution](evidence/attribution.json) are recorded separately. This is controlled evidence, with zero independent customers or revenue.

[VS Code MCP configuration](examples/vscode-mcp.json) prompts privately for the free token. The generic Agent Skill can also be installed in clients that read `SKILL.md`; no native VS Code GUI or other desktop client acceptance is claimed. Default Python `urllib` requests are blocked by Cloudflare error 1010; the standard MCP Python SDK, `httpx` and curl succeeded. No Cloudflare security setting was changed.

The [PHOENIX monitor](ops/phoenix_monitor.py) runs as an error-isolated post-command on the existing controller service, throttled to one network pass per 15 minutes. It records readback, usage, repeat tokens, per-seat responsibilities and explicit unknown hosting cost in the existing CRM. It reads existing demand feeds and never sends messages. See the [systemd drop-in](ops/systemd/40-payload-distribution.conf). Synthetic tests remain excluded from customer and installation totals.
