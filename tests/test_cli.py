from click.testing import CliRunner

from challenger.cli import main
from challenger.models import DailyResult, QualityGate


def blocked_result() -> DailyResult:
    return DailyResult(
        date="2026-08-30",
        generated_at="2026-08-30T20:00:00-04:00",
        project="Pantone Challenger",
        methodology_version="1.3.0",
        registry_version="1.3",
        panel_size=48,
        captured_sources=12,
        captured_sectors=5,
        baseline_days=0,
        calibration_day=0,
        status="blocked",
        confidence_label="Blocked",
        quality_gate=QualityGate(
            passed=False,
            reasons=["Not enough traceable evidence"],
            warnings=[],
            usable_sources=12,
            configured_sources=48,
            usable_sectors=5,
            configured_sectors=12,
            state="blocked",
            region_coverage_ratio=0.4,
        ),
        winner=None,
        winner_name=None,
        runners_up=[],
        source_failures=[],
        disclaimer="Independent",
    )


def test_blocked_daily_outcome_is_not_a_command_failure(monkeypatch):
    monkeypatch.setattr("challenger.cli.run_daily", lambda **_: blocked_result())
    response = CliRunner().invoke(main, ["run", "--date", "2026-08-30"])

    assert response.exit_code == 0
    assert '"status": "blocked"' in response.output
    assert "BLOCKED:" in response.output
