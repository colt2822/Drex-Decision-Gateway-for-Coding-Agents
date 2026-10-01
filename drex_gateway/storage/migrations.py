"""Database schema definitions and migrations for Drex Decision Gateway."""
from __future__ import annotations

import sqlite3

MIGRATIONS = [
    """
    -- Migration 1: Initial schema for decisions, probabilities, outcomes, traces, and benchmarks
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS traces (
        trace_id TEXT PRIMARY KEY,
        root_decision_id TEXT,
        agent_name TEXT,
        mission_id TEXT,
        task_id TEXT,
        repo TEXT,
        commit_sha TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS decisions (
        decision_id TEXT PRIMARY KEY,
        trace_id TEXT NOT NULL,
        parent_decision_id TEXT,
        decision_type TEXT NOT NULL,
        question_id TEXT NOT NULL,
        selected TEXT NOT NULL,
        confidence REAL NOT NULL,
        disposition TEXT NOT NULL,
        escalation_required INTEGER NOT NULL,
        model TEXT NOT NULL,
        provider TEXT NOT NULL,
        latency_ms REAL NOT NULL,
        provider_latency_ms REAL,
        gateway_overhead_ms REAL NOT NULL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        context_digest TEXT NOT NULL,
        state_text TEXT,
        would_have_used_expensive_model INTEGER NOT NULL DEFAULT 1,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_decisions_trace_id ON decisions(trace_id);
    CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
    CREATE INDEX IF NOT EXISTS idx_decisions_disposition ON decisions(disposition);
    CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at);

    CREATE TABLE IF NOT EXISTS decision_probabilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT NOT NULL,
        choice_key TEXT NOT NULL,
        probability REAL NOT NULL,
        FOREIGN KEY (decision_id) REFERENCES decisions(decision_id) ON DELETE CASCADE,
        UNIQUE (decision_id, choice_key)
    );

    CREATE INDEX IF NOT EXISTS idx_decision_probabilities_dec_id ON decision_probabilities(decision_id);

    CREATE TABLE IF NOT EXISTS outcomes (
        outcome_id TEXT PRIMARY KEY,
        decision_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        success INTEGER NOT NULL,
        expensive_model_actually_used INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (decision_id) REFERENCES decisions(decision_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_outcomes_decision_id ON outcomes(decision_id);

    CREATE TABLE IF NOT EXISTS provider_calls (
        call_id TEXT PRIMARY KEY,
        trace_id TEXT,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        latency_ms REAL NOT NULL,
        provider_latency_ms REAL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        error_kind TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_provider_calls_created ON provider_calls(created_at);

    CREATE TABLE IF NOT EXISTS benchmark_runs (
        run_id TEXT PRIMARY KEY,
        suite_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        total_cases INTEGER NOT NULL,
        accuracy REAL,
        coverage REAL,
        escalation_rate REAL,
        latency_p50 REAL,
        latency_p95 REAL,
        expensive_calls_avoided INTEGER,
        report_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply any pending migrations in a safe transaction."""
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);"
    )
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    applied = {row[0] for row in cursor.fetchall()}

    for version, migration_sql in enumerate(MIGRATIONS, start=1):
        if version not in applied:
            cursor.executescript(migration_sql)
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'));",
                (version,),
            )
    conn.commit()
