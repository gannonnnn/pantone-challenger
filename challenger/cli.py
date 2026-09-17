from __future__ import annotations

import json
import platform
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from challenger import __version__
from challenger.config import load_settings, load_sources, source_is_configured
from challenger.pipeline import DailyPipeline
from challenger.site import build_site
from challenger.annual import build_annual_summary
from challenger.social import publish_approved_day


app = typer.Typer(no_args_is_help=True, help="Pantone Challenger — the Open Cultural Color Index")
console = Console()


@app.command()
def doctor():
    """Validate configuration, dependencies, browser availability, and source readiness."""
    settings = load_settings()
    version, sources = load_sources()
    table = Table(title="Pantone Challenger doctor")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Application", f"v{__version__}")
    table.add_row("Python", platform.python_version())
    table.add_row("Registry", version)
    table.add_row("Enabled sources", str(sum(s.enabled for s in sources)))
    table.add_row("Configured enabled sources", str(sum(s.enabled and source_is_configured(s) for s in sources)))
    table.add_row("Benchmark / discovery", f"{sum(s.enabled and s.panel_type.value == 'benchmark' for s in sources)} / {sum(s.enabled and s.panel_type.value == 'discovery' for s in sources)}")
    table.add_row("Domains", str(len({s.domain.value for s in sources if s.enabled})))
    table.add_row("Signal stages", str(len({s.signal_stage.value for s in sources if s.enabled})))
    table.add_row("Chromium", "available" if _chromium_available() else "install with: playwright install chromium")
    console.print(table)


@app.command("run")
def run_daily(
    date: str = typer.Option("auto", help="Observation date in YYYY-MM-DD or 'auto' for today."),
    max_sources: int = typer.Option(0, min=0, help="0 uses the full selected panel."),
    rebuild: bool = typer.Option(False, help="Replace an existing archive date after successful validation."),
    resume: bool = typer.Option(False, help="Reuse verified successful captures from this date; retry failures."),
):
    """Run the live cultural-color pipeline."""
    pipeline = DailyPipeline()
    result = pipeline.run(run_date=date, max_sources=max_sources, rebuild=rebuild, resume=resume)
    console.print(f"State: [bold]{result.state.value}[/bold]")
    console.print(f"Coverage: {result.sources_with_eligible_evidence}/{result.panel_declared} active sources")
    if result.challenger:
        console.print("Challenger: " + " + ".join(f"{c.creative_name} {c.hex}" for c in result.challenger))
    else:
        console.print("No public Challenger selected.")
    console.print(f"Archive: archive/{result.date}")


@app.command("build-site")
def site(
    archive: Path = typer.Option(Path("archive")),
    destination: Path = typer.Option(Path("site-build")),
):
    """Build the historical GitHub Pages archive."""
    path = build_site(archive, destination)
    console.print(f"Site built: {path.resolve()}")


@app.command("validate-result")
def validate_result(path: Path):
    """Validate a stored daily result has the expected public structure."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"date", "state", "methodology_version", "registry_version", "palette_regime"}
    missing = required - payload.keys()
    if missing:
        raise typer.BadParameter(f"Missing keys: {', '.join(sorted(missing))}")
    if payload.get("state") == "ready" and not payload.get("challenger"):
        raise typer.BadParameter("A ready result requires at least one Challenger.")
    console.print("Result structure: OK")


def _chromium_available() -> bool:
    cache = Path.home() / ".cache" / "ms-playwright"
    return cache.exists() and any(cache.glob("chromium*"))


@app.command("resolve-date")
def resolve_date(value: str = "auto"):
    """Print the resolved marketing date for workflows."""
    console.print(DailyPipeline().resolve_date(value))


@app.command("year-end")
def year_end(
    year: int = typer.Option(..., help="Calendar year to summarize."),
    archive: Path = typer.Option(Path("archive")),
):
    """Generate the January Year in Color report."""
    summary = build_annual_summary(archive, year)
    console.print(f"Year-end summary built for {year}: {summary['approved_challenger_days']} approved days")


@app.command("publish")
def publish(
    date: str = typer.Option(...),
    platform: str = typer.Option(..., help="instagram or bluesky"),
    public_base_url: str = typer.Option("", envvar="PUBLIC_BASE_URL"),
    dry_run: bool = typer.Option(True),
):
    """Publish one approved ready result. Dry-run is the default."""
    result = publish_approved_day(date, platform, public_base_url=public_base_url or None, dry_run=dry_run)
    console.print_json(data=result)


@app.command("review-images")
def review_images_command(
    date: str = typer.Option(...),
    workdir: Path = typer.Option(Path(".work")),
    model: str = typer.Option("gpt-4.1-mini", envvar="OPENAI_VISION_MODEL"),
    limit: int = typer.Option(12, min=1, max=50),
    execute: bool = typer.Option(False, help="Send images to the OpenAI API; requires OPENAI_API_KEY. Default makes no calls."),
):
    """Create optional image-review suggestions. Never affects ranking or publication."""
    from datetime import date as Date
    from challenger.ai_review import review_images
    Date.fromisoformat(date)
    report = review_images(workdir / date, model=model, limit=limit, execute=execute)
    console.print_json(data={k: v for k, v in report.items() if k != "rows"})


@app.command("evaluate-ai")
def evaluate_ai_command(predictions: Path, labels: Path):
    """Compare shadow annotations with manually labelled, held-out examples."""
    from challenger.ai_review import evaluate_review
    console.print_json(data=evaluate_review(predictions, labels))


@app.command("sources")
def source_status(date: str = "auto"):
    """Show disabled, unconfigured, selected and rotating-out sources without secrets."""
    pipeline = DailyPipeline()
    active, _ = pipeline._select_sources(pipeline.resolve_date(date), 0)
    ids = {s.id for s in active}
    table = Table(title="Source readiness")
    for label in ["ID", "Adapter", "State", "Required secret name"]:
        table.add_column(label)
    for s in pipeline.sources:
        state = "disabled" if not s.enabled else "missing credentials" if not source_is_configured(s) else "selected" if s.id in ids else "rotating out"
        table.add_row(s.id, s.adapter, state, s.token_env or s.api_key_env or "—")
    console.print(table)
