"""Tests for coding agent workflows: Preflight, Patch Triage, Failure Triage, and Killer Demo."""
import pytest
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.workflows.failure_triage import FailureTriageWorkflow
from drex_gateway.workflows.killer_demo import KillerDemoRunner
from drex_gateway.workflows.patch_triage import PatchTriageWorkflow
from drex_gateway.workflows.preflight import PreflightWorkflow


@pytest.mark.asyncio
async def test_preflight_workflow(gateway: DrexDecisionGateway):
    wf = PreflightWorkflow(gateway)
    res = await wf.run(
        task_description="Add exponential backoff retry to auth token refresh requests in auth/client.py",
        repo_summary="Core auth service repository with endpoints in auth/routes.py and tests in tests/test_auth.py",
    )

    assert res.trace_id.startswith("preflight_")
    assert res.subsystem.selected == "auth"
    assert "TARGET SUBSYSTEM: AUTH" in res.codex_ready_context
    assert res.expensive_calls_avoided == 1
    assert res.total_drex_latency_ms >= 0.0


@pytest.mark.asyncio
async def test_patch_triage_workflow(gateway: DrexDecisionGateway):
    wf = PatchTriageWorkflow(gateway)
    diff = """
    --- a/auth/middleware.py
    +++ b/auth/middleware.py
    @@ -10,3 +10,6 @@
    +def check_header(request):
    +    return request.headers.get("X-Auth-Token") is not None
    """
    res = await wf.run(
        task_objective="Ensure X-Auth-Token header is present",
        patch_diff=diff,
        verifier_evidence="test passed in 0.1s",
    )

    assert res.trace_id.startswith("triage_")
    assert res.patch_scope.selected in ["too_narrow", "appropriate", "too_broad"]
    assert res.gating_action in ["PROCEED_TO_SUBMISSION", "ESCALATE_DEEP_REVIEW", "RETURN_TO_REPAIR"]


@pytest.mark.asyncio
async def test_failure_triage_environment_vs_implementation(gateway: DrexDecisionGateway):
    wf = FailureTriageWorkflow(gateway)

    # 1. Environment failure test
    env_res = await wf.run(
        objective="Fix user login",
        changed_files=["auth/login.py"],
        verifier_command="pytest",
        exit_code=1,
        stdout_stderr="ModuleNotFoundError: No module named 'jwt'",
    )
    assert env_res.failure_classification.selected == "environment_failure"
    assert env_res.recommended_action in ["ESCALATE", "WAIT_FOR_RESOURCE"]
    assert env_res.expensive_calls_avoided == 1  # Blocked code repair attempt for env error!

    # 2. Implementation defect test
    impl_res = await wf.run(
        objective="Fix user login",
        changed_files=["auth/login.py"],
        verifier_command="pytest",
        exit_code=1,
        stdout_stderr="AssertionError: assert 401 == 200 in tests/test_login.py line 24",
    )
    assert impl_res.failure_classification.selected == "implementation_failure"
    assert impl_res.recommended_action == "REPAIR"


@pytest.mark.asyncio
async def test_killer_demo_runner(gateway: DrexDecisionGateway):
    runner = KillerDemoRunner(gateway)
    report = await runner.run()

    assert report.total_drex_decisions >= 3
    assert report.final_status == "VERIFIER_PASS"
    assert report.expensive_calls_avoided >= 1
    assert len(report.steps) >= 7
    assert report.trace_summary is not None
