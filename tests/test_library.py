"""Tests for the 14 Coding-Agent Decision Library schemas."""
from drex_gateway.library.schemas import (
    make_task_complexity_question,
    make_tool_selection_question,
    make_repository_area_question,
    make_test_selection_question,
    make_verifier_selection_question,
    make_failure_classification_question,
    make_next_action_question,
    make_patch_risk_question,
    make_review_readiness_question,
    make_ci_failure_attribution_question,
    make_architecture_escalation_question,
    make_more_context_required_question,
    make_patch_scope_class_question,
    make_maintainer_risk_question,
)


def test_library_schemas():
    # 1. TASK_COMPLEXITY
    tc = make_task_complexity_question()
    assert set(tc.criteria.keys()) == {"trivial", "standard", "large_context", "architecture_heavy"}

    # 2. TOOL_SELECTION
    ts = make_tool_selection_question({"grep": "search text", "view_file": "read file"})
    assert "grep" in ts.criteria

    # 3. REPOSITORY_AREA
    ra = make_repository_area_question({"auth": "auth logic", "billing": "payments"})
    assert "auth" in ra.criteria

    # 4. TEST_SELECTION
    test_sel = make_test_selection_question({"unit": "unit tests", "integration": "integration"})
    assert "unit" in test_sel.criteria

    # 5. VERIFIER_SELECTION
    vs = make_verifier_selection_question()
    assert "unit_test" in vs.criteria
    assert "full_ci_harness" in vs.criteria

    # 6. FAILURE_CLASSIFICATION
    fc = make_failure_classification_question()
    assert "implementation_failure" in fc.criteria
    assert "environment_failure" in fc.criteria
    assert "toolchain_failure" in fc.criteria

    # 7. NEXT_ACTION
    na = make_next_action_question()
    assert "repair" in na.criteria
    assert "replan" in na.criteria
    assert "escalate" in na.criteria

    # 8. PATCH_RISK
    pr = make_patch_risk_question()
    assert pr.type == "score"
    assert len(pr.criteria) >= 3

    # 9. REVIEW_READINESS
    rr = make_review_readiness_question()
    assert "ready" in rr.criteria
    assert "needs_deep_review" in rr.criteria

    # 10. CI_FAILURE_ATTRIBUTION
    ci = make_ci_failure_attribution_question()
    assert "patch_caused" in ci.criteria
    assert "baseline" in ci.criteria

    # 11. ARCHITECTURE_ESCALATION
    ae = make_architecture_escalation_question()
    assert ae.type == "noul"

    # 12. MORE_CONTEXT_REQUIRED
    mc = make_more_context_required_question()
    assert mc.type == "noul"

    # 13. PATCH_SCOPE_CLASS
    psc = make_patch_scope_class_question()
    assert set(psc.criteria.keys()) == {"too_narrow", "appropriate", "too_broad"}

    # 14. MAINTAINER_RISK
    mr = make_maintainer_risk_question()
    assert set(mr.criteria.keys()) == {"low", "medium", "high"}
