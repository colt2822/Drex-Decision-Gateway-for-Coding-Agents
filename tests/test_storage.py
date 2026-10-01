"""Tests for SQLite database persistence, WAL mode, probability preservation, outcomes, and concurrency."""
import concurrent.futures
import uuid
import pytest
from drex_gateway.models import DecisionResult, Disposition
from drex_gateway.storage.db import Database


def test_decision_and_probability_preservation(test_db: Database):
    dec_id = str(uuid.uuid4())
    trace_id = "test_trace_123"

    res = DecisionResult(
        decision_id=dec_id,
        trace_id=trace_id,
        decision_type="TEST_SELECTION",
        question_id="test_suite",
        selected="pytest",
        confidence=0.91,
        probabilities={"pytest": 0.91, "npm": 0.06, "cargo": 0.03},
        disposition=Disposition.ACCEPT,
        escalation_required=False,
        model="drex-latest",
        provider="Drex",
        latency_ms=85.2,
        provider_latency_ms=75.0,
        gateway_overhead_ms=10.2,
        context_digest="abcd1234",
    )

    test_db.record_decision(res, state_text="Full repo state context")

    # Retrieve and verify full fidelity
    loaded = test_db.get_decision(dec_id)
    assert loaded is not None
    assert loaded.decision_id == dec_id
    assert loaded.decision_type == "TEST_SELECTION"
    assert loaded.selected == "pytest"
    assert loaded.confidence == 0.91
    assert loaded.probabilities == {"pytest": 0.91, "npm": 0.06, "cargo": 0.03}
    assert loaded.disposition == Disposition.ACCEPT
    assert loaded.escalation_required is False
    assert loaded.provider == "Drex"


def test_outcome_recording_and_trace_summary(test_db: Database):
    dec_id = str(uuid.uuid4())
    trace_id = "trace_abc_456"

    res = DecisionResult(
        decision_id=dec_id,
        trace_id=trace_id,
        decision_type="REVIEW_READINESS",
        question_id="ready_check",
        selected="ready",
        confidence=0.96,
        probabilities={"ready": 0.96, "needs_repair": 0.04},
        disposition=Disposition.ACCEPT,
        escalation_required=False,
        model="drex-latest",
        provider="Drex",
        latency_ms=90.0,
        gateway_overhead_ms=5.0,
        context_digest="digest_456",
        would_have_used_expensive_model=True,
    )
    test_db.record_decision(res)

    # Attach outcome
    outcome = test_db.record_outcome(
        decision_id=dec_id,
        outcome="VERIFIER_PASS",
        success=True,
        expensive_model_actually_used=False,
        metadata={"build_duration": 4.2},
    )
    assert outcome.outcome == "VERIFIER_PASS"
    assert outcome.success is True

    # Check TraceSummary
    summary = test_db.get_trace_summary(trace_id)
    assert summary is not None
    assert summary.trace_id == trace_id
    assert summary.total_drex_decisions == 1
    assert summary.accepted_count == 1
    assert summary.expensive_calls_avoided == 1
    assert len(summary.outcomes) == 1
    assert summary.outcomes[0].outcome == "VERIFIER_PASS"


def test_concurrent_writes(test_db: Database):
    def insert_worker(i: int):
        dec_id = f"dec_concurrent_{i}_{uuid.uuid4().hex[:6]}"
        res = DecisionResult(
            decision_id=dec_id,
            trace_id=f"trace_{i}",
            decision_type="CONCURRENT_TYPE",
            question_id="q",
            selected="opt1",
            confidence=0.88,
            probabilities={"opt1": 0.88, "opt2": 0.12},
            disposition=Disposition.ACCEPT,
            escalation_required=False,
            model="drex-latest",
            provider="REPLAY",
            latency_ms=10.0 + i,
            context_digest="dig",
        )
        test_db.record_decision(res)
        return dec_id

    # Execute 20 concurrent inserts across threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(insert_worker, i) for i in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    stats = test_db.get_stats()
    assert stats["total_decisions"] >= 20
