"""Tests for Click CLI commands."""
from click.testing import CliRunner
from drex_gateway.cli.main import cli


def test_cli_health(tmp_path):
    db_file = str(tmp_path / "cli.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", db_file, "--replay", "health"])
    assert result.exit_code == 0
    assert "Gateway Status: HEALTHY" in result.output
    assert "REPLAY" in result.output


def test_cli_choose(tmp_path):
    db_file = str(tmp_path / "cli.db")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--db",
            db_file,
            "--replay",
            "choose",
            "Which verifier?",
            "-c",
            "pytest,npm_test",
            "-x",
            "Python tests",
        ],
    )
    assert result.exit_code == 0
    assert "Decision Result" in result.output
    assert "Selected:" in result.output


def test_cli_stats(tmp_path):
    db_file = str(tmp_path / "cli.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", db_file, "--replay", "stats"])
    assert result.exit_code == 0
    assert "DREX DECISION GATEWAY METRICS" in result.output


def test_cli_benchmark(tmp_path):
    db_file = str(tmp_path / "cli.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", db_file, "--replay", "benchmark"])
    assert result.exit_code == 0
    assert "BENCHMARK RESULTS" in result.output
    assert "THRESHOLD ESCALATION SIMULATION" in result.output


def test_cli_demo(tmp_path):
    db_file = str(tmp_path / "cli.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", db_file, "--replay", "demo"])
    assert result.exit_code == 0
    assert "KILLER DEMO EXECUTION SUMMARY" in result.output
    assert "VERIFIER_PASS" in result.output
