"""Regression tests for independently reproduced Gateway audit findings."""

import sqlite3
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from drex_gateway.benchmarks.runner import BenchmarkCase, BenchmarkRunner
from drex_gateway.config import GatewayConfig
from drex_gateway.errors import ProviderError
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import BatchDecisionRequest, ChoiceQuestion, DecisionResult, Disposition
from drex_gateway.providers.replay import ReplayProvider
from drex_gateway.sdk.client import DrexGateway


@pytest.mark.asyncio
async def test_gateway_rejects_malformed_provider_confidence_and_probabilities(tmp_path):
    db_path = str(tmp_path / "malformed.db")
    provider = ReplayProvider(
        canned_fixtures={
            "choose_primary": {
                "type": "choice",
                "choice": "a",
                "confidence": 9.0,
                "probabilities": {"a": -4.0, "b": 5.0},
            }
        }
    )
    gateway = DrexDecisionGateway(
        config=GatewayConfig(db_path=db_path, force_provider="REPLAY"),
        provider=provider,
    )

    with pytest.raises(ProviderError):
        await gateway.choose("select", ["a", "b"], "context")


def test_record_decision_rolls_back_when_probability_insert_fails(test_db):
    conn = test_db._get_connection()
    conn.execute(
        "CREATE TRIGGER reject_probability BEFORE INSERT ON decision_probabilities "
        "BEGIN SELECT RAISE(ABORT, 'injected probability failure'); END;"
    )
    decision = DecisionResult(
        decision_id="audit_decision",
        trace_id="audit_trace",
        decision_type="test",
        question_id="q",
        selected="a",
        confidence=0.9,
        probabilities={"a": 0.9, "b": 0.1},
        disposition=Disposition.ACCEPT,
        escalation_required=False,
        model="replay",
        provider="REPLAY",
        latency_ms=1.0,
        context_digest="digest",
    )

    with pytest.raises(sqlite3.IntegrityError):
        test_db.record_decision(decision)

    assert conn.execute("SELECT count(*) FROM decisions").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_batch_decision_is_atomic_when_later_insert_fails(test_db, tmp_path):
    conn = test_db._get_connection()
    conn.execute(
        "CREATE TRIGGER reject_second_decision BEFORE INSERT ON decisions "
        "WHEN NEW.question_id = 'second' "
        "BEGIN SELECT RAISE(ABORT, 'injected second decision failure'); END;"
    )
    gateway = DrexDecisionGateway(
        config=GatewayConfig(db_path=str(tmp_path / "batch.db"), force_provider="REPLAY"),
        provider=ReplayProvider(),
        db=test_db,
    )
    question = ChoiceQuestion(type="choice", instructions="choose", criteria={"a": None, "b": None})

    with pytest.raises(sqlite3.IntegrityError):
        await gateway.batch_decide(
            BatchDecisionRequest(
                state="context",
                questions={"first": question, "second": question},
            )
        )

    assert conn.execute("SELECT count(*) FROM decisions").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 0


class _BenchmarkGateway:
    def __init__(self):
        self.provider = SimpleNamespace(provider_name="REPLAY", default_model="replay")
        self.db = SimpleNamespace(record_benchmark_run=lambda **kwargs: None)
        self.calls = []

    async def _result(self, method, question_id):
        self.calls.append((method, question_id))
        if method == "yes_no":
            selected = "NO"
            disposition = Disposition.ABSTAIN
        elif method == "rate":
            selected = "1"
            disposition = Disposition.ACCEPT
        else:
            selected = "expected"
            disposition = Disposition.ACCEPT
        return DecisionResult(
            decision_id=f"decision-{question_id}",
            trace_id="benchmark",
            decision_type="benchmark",
            question_id=question_id,
            selected=selected,
            confidence=0.8,
            probabilities={"expected": 0.8, "other": 0.2},
            disposition=disposition,
            escalation_required=disposition == Disposition.ESCALATE,
            model="replay",
            provider="REPLAY",
            latency_ms=1.0,
            context_digest="digest",
        )

    async def choose(self, *, question_id, **kwargs):
        return await self._result("choose", question_id)

    async def yes_no(self, question, context, *, question_id, **kwargs):
        return await self._result("yes_no", question_id)

    async def rate(self, question, criteria, context, *, question_id, **kwargs):
        return await self._result("rate", question_id)


@pytest.mark.asyncio
async def test_benchmark_dispatches_each_question_type_to_its_typed_primitive():
    gateway = _BenchmarkGateway()
    cases = [
        BenchmarkCase(
            id="choice-case",
            context="context",
            question_type="choice",
            instructions="pick",
            criteria={"expected": "Expected", "other": "Other"},
            expected_answer="expected",
        ),
        BenchmarkCase(
            id="noul-case",
            context="context",
            question_type="noul",
            instructions="yes or no",
            expected_answer="YES",
        ),
        BenchmarkCase(
            id="score-case",
            context="context",
            question_type="score",
            instructions="rate",
            criteria=["low", "high"],
            expected_answer="1",
        ),
    ]

    report = await BenchmarkRunner(gateway).run(cases)

    assert gateway.calls == [
        ("choose", "choice-case"),
        ("yes_no", "noul-case"),
        ("rate", "score-case"),
    ]
    assert report.accuracy == 1.0


def test_invalid_explicit_provider_mode_is_rejected():
    with pytest.raises(PydanticValidationError):
        GatewayConfig(force_provider="REPLAYE")

    assert GatewayConfig(force_provider="replay").force_provider == "REPLAY"


def test_sdk_api_key_argument_configures_local_provider_without_exposing_key(tmp_path):
    key = "nace_sk_" + "A" * 43
    client = DrexGateway(api_key=key, db_path=str(tmp_path / "sdk.db"))

    assert client._local.provider_mode == "LIVE"
    assert client._local.config.get_api_key() == key
    assert key not in repr(client._local.config)
    client._local.db.close()
