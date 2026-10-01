#!/usr/bin/env python3
"""Patch Triage Example using Drex Decision Gateway.

After a generative coding model (e.g. Codex or Claude) produces a diff,
Drex evaluates the candidate patch in a single batched roundtrip:
1. Patch Scope: Is it too narrow, appropriate, or too broad?
2. Implementation Completeness: Did it actually fulfill the task?
3. Patch Risk: Numeric risk scoring (1-5 scale).
4. Missing Tests: Are companion tests missing?
5. Review Readiness: Ready, needs repair, or needs deep human review?
6. Maintainer Risk: Low, medium, high blast radius?

This yields a fast gating action (PROCEED_TO_SUBMISSION, RETURN_TO_REPAIR, ESCALATE_DEEP_REVIEW).
"""
from drex_gateway.sdk.client import DrexGateway


def main():
    client = DrexGateway()

    diff = """
--- a/auth/tokens.py
+++ b/auth/tokens.py
@@ -42,7 +42,7 @@ def verify_jwt(token: str) -> dict:
     payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
-    if payload.get("exp") < time.time():
+    if payload.get("exp") <= time.time():
         raise TokenExpiredError("Token has expired")
     return payload
--- a/tests/test_tokens.py
+++ b/tests/test_tokens.py
@@ -88,3 +88,7 @@ def test_token_expiration_boundary():
+    token = create_token(expires_in=0)
+    with pytest.raises(TokenExpiredError):
+        verify_jwt(token)
"""

    print("=== Drex Decision Gateway: Patch Triage Example ===\n")
    print("Evaluating candidate patch and test evidence...")

    triage = client.patch_triage(
        task_objective="Fix off-by-one boundary condition where expired tokens at current second are accepted",
        patch_diff=diff,
        verifier_evidence="pytest tests/test_tokens.py passed with 14 passed in 0.42s",
    )

    print(f"Trace ID:            {triage.trace_id}")
    print(f"Gating Action:       {triage.gating_action}")
    print(f"Patch Scope:         {triage.patch_scope.selected} (conf: {triage.patch_scope.confidence:.2%})")
    print(f"Complete:            {triage.implementation_complete.selected}")
    print(f"Missing Tests:       {triage.missing_tests.selected}")
    print(f"Review Readiness:    {triage.review_readiness.selected} (conf: {triage.review_readiness.confidence:.2%})")
    print(f"Maintainer Risk:     {triage.maintainer_risk.selected}")
    print(f"Total Drex Latency:  {triage.total_drex_latency_ms:.1f}ms")


if __name__ == "__main__":
    main()
