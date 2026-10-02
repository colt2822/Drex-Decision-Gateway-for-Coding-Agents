# Security Policy

## Supported Versions

| Version | Supported          |
| :---    | :---               |
| 0.1.x   | :white_check_mark: |

---

The HTTP API has no built-in authentication. The CLI binds to loopback by default, and browser cross-origin access is disabled unless exact origins are configured through `DREX_CORS_ORIGINS`. Deployments that bind to a network interface must supply independent authentication and access controls.

## Reporting a Vulnerability

We take the security of **Drex Decision Gateway** seriously. If you discover a security vulnerability or potential credential leak:

**Please do NOT open a public GitHub issue.**

Instead, report it privately using one of the following methods:

1. **GitHub Private Vulnerability Reporting (Preferred):**
   Navigate to the [Security Advisories](https://github.com/colt2822/Drex-Decision-Gateway-for-Coding-Agents/security/advisories/new) page of the repository and click **"Report a vulnerability"**.

2. **Maintainer Contact:**
   If private vulnerability reporting is unavailable, contact the repository maintainers via GitHub discussion or direct maintainer profile message before disclosing any details publicly.

### What to Include

Please provide:
- A clear description of the vulnerability.
- Minimal reproducible steps or a proof of concept.
- Affected components (HTTP API, SDK, CLI, MCP server, SQLite storage).
- Any potential impact on authentication or data exposure.

We will acknowledge receipt within 48 hours and work with you on a coordinated disclosure timeline and fix.

---

## Security Practices in Drex Gateway

1. **Zero Credential Logging:** Secrets (`DREX_API_KEY`) are never stored in SQLite database tables, Prometheus metrics, or debug traces.
2. **Key File Permissions:** API key files must have strict POSIX permissions (`0600` or `0400`) and are rejected if readable by other users.
3. **Local Database Isolation:** SQLite databases are created with local file permissions and support WAL mode for concurrency safety.
