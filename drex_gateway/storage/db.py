"""Thread-safe SQLite database manager for Drex Decision Gateway."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from drex_gateway.models import (
    DecisionResult,
    Disposition,
    OutcomeRecord,
    TraceSummary,
)
from drex_gateway.storage.migrations import apply_migrations


class Database:
    """SQLite storage wrapper with connection pooling per thread and WAL mode."""

    def __init__(self, db_path: str = "drex_gateway.db"):
        self.db_path = db_path
        self._local = threading.local()
        # Initialize schema
        conn = self._get_connection()
        apply_migrations(conn)

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            # Ensure parent directories exist
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode, normal synchronous, and foreign keys
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def record_trace(
        self,
        trace_id: str,
        *,
        root_decision_id: str | None = None,
        agent_name: str | None = None,
        mission_id: str | None = None,
        task_id: str | None = None,
        repo: str | None = None,
        commit_sha: str | None = None,
    ) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO traces (trace_id, root_decision_id, agent_name, mission_id, task_id, repo, commit_sha, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(trace_id) DO UPDATE SET
                    root_decision_id = COALESCE(excluded.root_decision_id, traces.root_decision_id),
                    agent_name = COALESCE(excluded.agent_name, traces.agent_name),
                    mission_id = COALESCE(excluded.mission_id, traces.mission_id),
                    task_id = COALESCE(excluded.task_id, traces.task_id),
                    repo = COALESCE(excluded.repo, traces.repo),
                    commit_sha = COALESCE(excluded.commit_sha, traces.commit_sha),
                    updated_at = datetime('now');
                """,
                (trace_id, root_decision_id, agent_name, mission_id, task_id, repo, commit_sha),
            )

    def record_decision(self, decision: DecisionResult, state_text: str | None = None) -> None:
        self.record_decisions([decision], state_text=state_text)

    def record_decisions(self, decisions: list[DecisionResult], state_text: str | None = None) -> None:
        """Persist decisions, traces, and probabilities in one SQLite transaction."""
        conn = self._get_connection()
        with conn:
            for decision in decisions:
                self._insert_decision(conn, decision, state_text)

    @staticmethod
    def _insert_decision(
        conn: sqlite3.Connection,
        decision: DecisionResult,
        state_text: str | None,
    ) -> None:
        # Ensure trace exists
        conn.execute(
            """
            INSERT OR IGNORE INTO traces (trace_id, root_decision_id, created_at, updated_at)
            VALUES (?, ?, datetime('now'), datetime('now'));
            """,
            (decision.trace_id, decision.decision_id),
        )

        conn.execute(
            """
            INSERT INTO decisions (
                decision_id, trace_id, parent_decision_id, decision_type, question_id,
                selected, confidence, disposition, escalation_required, model, provider,
                latency_ms, provider_latency_ms, gateway_overhead_ms, input_tokens, output_tokens,
                context_digest, state_text, would_have_used_expensive_model, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                decision.decision_id,
                decision.trace_id,
                decision.parent_decision_id,
                decision.decision_type,
                decision.question_id,
                str(decision.selected),
                float(decision.confidence),
                decision.disposition.value,
                1 if decision.escalation_required else 0,
                decision.model,
                decision.provider,
                float(decision.latency_ms),
                float(decision.provider_latency_ms) if decision.provider_latency_ms is not None else None,
                float(decision.gateway_overhead_ms),
                decision.input_tokens,
                decision.output_tokens,
                decision.context_digest,
                state_text[:65536] if state_text else None,
                1 if decision.would_have_used_expensive_model else 0,
                json.dumps(decision.metadata),
                decision.created_at,
            ),
        )

        for key, prob in decision.probabilities.items():
            conn.execute(
                """
                INSERT INTO decision_probabilities (decision_id, choice_key, probability)
                VALUES (?, ?, ?)
                ON CONFLICT(decision_id, choice_key) DO UPDATE SET probability = excluded.probability;
                """,
                (decision.decision_id, key, float(prob)),
            )

    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        success: bool,
        *,
        expensive_model_actually_used: bool | None = None,
        metadata: dict[str, Any] | None = None,
        outcome_id: str | None = None,
    ) -> OutcomeRecord:
        outcome_id = outcome_id or str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO outcomes (outcome_id, decision_id, outcome, success, expensive_model_actually_used, metadata_json, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'));
                """,
                (
                    outcome_id,
                    decision_id,
                    outcome,
                    1 if success else 0,
                    (1 if expensive_model_actually_used else 0) if expensive_model_actually_used is not None else None,
                    metadata_json,
                ),
            )
            row = conn.execute("SELECT recorded_at FROM outcomes WHERE outcome_id = ?;", (outcome_id,)).fetchone()
            recorded_at = row["recorded_at"] if row else ""

        return OutcomeRecord(
            outcome_id=outcome_id,
            decision_id=decision_id,
            outcome=outcome,
            success=success,
            expensive_model_actually_used=expensive_model_actually_used,
            metadata=metadata or {},
            recorded_at=recorded_at,
        )

    def record_provider_call(
        self,
        call_id: str,
        *,
        trace_id: str | None = None,
        provider: str,
        model: str,
        endpoint: str,
        status_code: int,
        latency_ms: float,
        provider_latency_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_kind: str | None = None,
        error_message: str | None = None,
    ) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO provider_calls (
                    call_id, trace_id, provider, model, endpoint, status_code,
                    latency_ms, provider_latency_ms, input_tokens, output_tokens,
                    error_kind, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
                """,
                (
                    call_id,
                    trace_id,
                    provider,
                    model,
                    endpoint,
                    status_code,
                    latency_ms,
                    provider_latency_ms,
                    input_tokens,
                    output_tokens,
                    error_kind,
                    error_message,
                ),
            )

    def record_benchmark_run(
        self,
        run_id: str,
        suite_name: str,
        provider: str,
        model: str,
        total_cases: int,
        accuracy: float | None,
        coverage: float | None,
        escalation_rate: float | None,
        latency_p50: float | None,
        latency_p95: float | None,
        expensive_calls_avoided: int,
        report_json: str,
    ) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO benchmark_runs (
                    run_id, suite_name, provider, model, total_cases, accuracy,
                    coverage, escalation_rate, latency_p50, latency_p95,
                    expensive_calls_avoided, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
                """,
                (
                    run_id,
                    suite_name,
                    provider,
                    model,
                    total_cases,
                    accuracy,
                    coverage,
                    escalation_rate,
                    latency_p50,
                    latency_p95,
                    expensive_calls_avoided,
                    report_json,
                ),
            )

    def get_decision(self, decision_id: str) -> DecisionResult | None:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?;", (decision_id,)).fetchone()
        if not row:
            return None
        return self._row_to_decision(row, conn)

    def _row_to_decision(self, row: sqlite3.Row, conn: sqlite3.Connection) -> DecisionResult:
        dec_id = row["decision_id"]
        prob_rows = conn.execute(
            "SELECT choice_key, probability FROM decision_probabilities WHERE decision_id = ?;",
            (dec_id,),
        ).fetchall()
        probabilities = {pr["choice_key"]: pr["probability"] for pr in prob_rows}

        meta = {}
        if row["metadata_json"]:
            try:
                meta = json.loads(row["metadata_json"])
            except Exception:
                meta = {}

        return DecisionResult(
            decision_id=row["decision_id"],
            trace_id=row["trace_id"],
            parent_decision_id=row["parent_decision_id"],
            decision_type=row["decision_type"],
            question_id=row["question_id"],
            selected=row["selected"],
            confidence=row["confidence"],
            probabilities=probabilities,
            disposition=Disposition(row["disposition"]),
            escalation_required=bool(row["escalation_required"]),
            model=row["model"],
            provider=row["provider"],
            latency_ms=row["latency_ms"],
            provider_latency_ms=row["provider_latency_ms"],
            gateway_overhead_ms=row["gateway_overhead_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            context_digest=row["context_digest"],
            would_have_used_expensive_model=bool(row["would_have_used_expensive_model"]),
            metadata=meta,
            created_at=row["created_at"],
        )

    def list_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        decision_type: str | None = None,
        disposition: str | None = None,
    ) -> list[DecisionResult]:
        conn = self._get_connection()
        query = "SELECT * FROM decisions WHERE 1=1"
        params: list[Any] = []
        if decision_type:
            query += " AND decision_type = ?"
            params.append(decision_type)
        if disposition:
            query += " AND disposition = ?"
            params.append(disposition)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_decision(r, conn) for r in rows]

    def get_trace_summary(self, trace_id: str) -> TraceSummary | None:
        conn = self._get_connection()
        trace_row = conn.execute("SELECT * FROM traces WHERE trace_id = ?;", (trace_id,)).fetchone()
        if not trace_row:
            return None

        dec_rows = conn.execute(
            "SELECT * FROM decisions WHERE trace_id = ? ORDER BY created_at ASC;",
            (trace_id,),
        ).fetchall()
        decisions = [self._row_to_decision(r, conn) for r in dec_rows]

        outcome_rows = conn.execute(
            """
            SELECT o.* FROM outcomes o
            JOIN decisions d ON o.decision_id = d.decision_id
            WHERE d.trace_id = ?
            ORDER BY o.recorded_at ASC;
            """,
            (trace_id,),
        ).fetchall()

        outcomes = []
        for o in outcome_rows:
            meta = {}
            if o["metadata_json"]:
                try:
                    meta = json.loads(o["metadata_json"])
                except Exception:
                    pass
            outcomes.append(
                OutcomeRecord(
                    outcome_id=o["outcome_id"],
                    decision_id=o["decision_id"],
                    outcome=o["outcome"],
                    success=bool(o["success"]),
                    expensive_model_actually_used=bool(o["expensive_model_actually_used"])
                    if o["expensive_model_actually_used"] is not None
                    else None,
                    metadata=meta,
                    recorded_at=o["recorded_at"],
                )
            )

        total_drex = len(decisions)
        accepted = sum(1 for d in decisions if d.disposition == Disposition.ACCEPT)
        escalated = sum(1 for d in decisions if d.disposition == Disposition.ESCALATE)
        abstained = sum(1 for d in decisions if d.disposition == Disposition.ABSTAIN)

        # Avoided = decisions that were accepted where would_have_used_expensive_model was True
        avoided = sum(
            1 for d in decisions if d.disposition == Disposition.ACCEPT and d.would_have_used_expensive_model
        )
        total_latency = sum(d.latency_ms for d in decisions)

        return TraceSummary(
            trace_id=trace_id,
            root_decision_id=trace_row["root_decision_id"],
            decisions=decisions,
            outcomes=outcomes,
            total_drex_decisions=total_drex,
            accepted_count=accepted,
            escalated_count=escalated,
            abstained_count=abstained,
            expensive_calls_avoided=avoided,
            total_latency_ms=round(total_latency, 2),
            agent_name=trace_row["agent_name"],
            repo=trace_row["repo"],
            commit_sha=trace_row["commit_sha"],
            created_at=trace_row["created_at"],
        )

    def get_stats(self) -> dict[str, Any]:
        """Compute system-wide statistics, latency percentiles, and avoidance rate."""
        conn = self._get_connection()
        total_decisions = conn.execute("SELECT COUNT(*) FROM decisions;").fetchone()[0]

        if total_decisions == 0:
            return {
                "total_decisions": 0,
                "accepted_count": 0,
                "escalated_count": 0,
                "abstained_count": 0,
                "expensive_calls_avoided": 0,
                "escalation_rate": 0.0,
                "accept_rate": 0.0,
                "latency_p50_ms": None,
                "latency_p95_ms": None,
                "provider_latency_p50_ms": None,
                "provider_latency_p95_ms": None,
                "gateway_overhead_p50_ms": None,
                "gateway_overhead_p95_ms": None,
                "decision_types": {},
                "providers": {},
                "models": {},
                "outcomes_count": 0,
                "success_rate": None,
            }

        counts_row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN disposition = 'ACCEPT' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN disposition = 'ESCALATE' THEN 1 ELSE 0 END) as escalated,
                SUM(CASE WHEN disposition = 'ABSTAIN' THEN 1 ELSE 0 END) as abstained,
                SUM(CASE WHEN disposition = 'ACCEPT' AND would_have_used_expensive_model = 1 THEN 1 ELSE 0 END) as avoided
            FROM decisions;
            """
        ).fetchone()

        accepted = counts_row["accepted"] or 0
        escalated = counts_row["escalated"] or 0
        abstained = counts_row["abstained"] or 0
        avoided = counts_row["avoided"] or 0

        # Latencies
        latencies = [r[0] for r in conn.execute("SELECT latency_ms FROM decisions ORDER BY latency_ms ASC;").fetchall()]
        overheads = [r[0] for r in conn.execute("SELECT gateway_overhead_ms FROM decisions ORDER BY gateway_overhead_ms ASC;").fetchall()]
        prov_latencies = [
            r[0]
            for r in conn.execute(
                "SELECT provider_latency_ms FROM decisions WHERE provider_latency_ms IS NOT NULL ORDER BY provider_latency_ms ASC;"
            ).fetchall()
        ]

        def percentile(vals: list[float], pct: float) -> float | None:
            if not vals:
                return None
            idx = int(len(vals) * pct)
            idx = min(idx, len(vals) - 1)
            return round(vals[idx], 2)

        type_rows = conn.execute(
            "SELECT decision_type, COUNT(*) as cnt FROM decisions GROUP BY decision_type;"
        ).fetchall()
        decision_types = {r["decision_type"]: r["cnt"] for r in type_rows}

        provider_rows = conn.execute("SELECT provider, COUNT(*) as cnt FROM decisions GROUP BY provider;").fetchall()
        providers = {r["provider"]: r["cnt"] for r in provider_rows}

        model_rows = conn.execute("SELECT model, COUNT(*) as cnt FROM decisions GROUP BY model;").fetchall()
        models = {r["model"]: r["cnt"] for r in model_rows}

        outcome_stats = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as passed FROM outcomes;"
        ).fetchone()
        outcomes_count = outcome_stats["total"] or 0
        passed_count = outcome_stats["passed"] or 0
        success_rate = round(passed_count / outcomes_count, 4) if outcomes_count > 0 else None

        return {
            "total_decisions": total_decisions,
            "accepted_count": accepted,
            "escalated_count": escalated,
            "abstained_count": abstained,
            "expensive_calls_avoided": avoided,
            "escalation_rate": round(escalated / total_decisions, 4) if total_decisions else 0.0,
            "accept_rate": round(accepted / total_decisions, 4) if total_decisions else 0.0,
            "latency_p50_ms": percentile(latencies, 0.50),
            "latency_p95_ms": percentile(latencies, 0.95),
            "provider_latency_p50_ms": percentile(prov_latencies, 0.50),
            "provider_latency_p95_ms": percentile(prov_latencies, 0.95),
            "gateway_overhead_p50_ms": percentile(overheads, 0.50),
            "gateway_overhead_p95_ms": percentile(overheads, 0.95),
            "decision_types": decision_types,
            "providers": providers,
            "models": models,
            "outcomes_count": outcomes_count,
            "success_rate": success_rate,
        }

    def list_benchmark_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM benchmark_runs ORDER BY created_at DESC LIMIT ?;",
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            rep = {}
            if r["report_json"]:
                try:
                    rep = json.loads(r["report_json"])
                except Exception:
                    pass
            results.append({
                "run_id": r["run_id"],
                "suite_name": r["suite_name"],
                "provider": r["provider"],
                "model": r["model"],
                "total_cases": r["total_cases"],
                "accuracy": r["accuracy"],
                "coverage": r["coverage"],
                "escalation_rate": r["escalation_rate"],
                "latency_p50": r["latency_p50"],
                "latency_p95": r["latency_p95"],
                "expensive_calls_avoided": r["expensive_calls_avoided"],
                "created_at": r["created_at"],
                "report": rep,
            })
        return results
