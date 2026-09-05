from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

import click

from . import __version__
from .annual import write_annual_package
from .config import load_settings, load_sources, panel_summary
from .pipeline import run_daily
from .publish.bluesky import publish_bluesky
from .publish.common import PublishError
from .publish.instagram import publish_instagram
from .site import build_site


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Measure yesterday's unusually prominent color across commercial marketing."""


@main.command("doctor")
@click.option("--config-dir", type=click.Path(path_type=Path), default=Path("config"))
def doctor(config_dir: Path) -> None:
    """Check configuration and runtime prerequisites."""
    settings = load_settings(config_dir)
    sources = load_sources(config_dir)
    summary = panel_summary(sources)
    click.echo(f"Pantone Challenger {__version__}")
    click.echo(f"Python: {platform.python_version()}")
    click.echo(f"Timezone: {settings.timezone} (rollover {settings.rollover_hour}:00)")
    click.echo(f"Live panel: {summary['sources']} sources / {summary['sectors']} sectors")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
        click.echo("Playwright package: installed")
        if not executable.exists():
            raise click.ClickException(
                "Chromium is not installed. Run `python -m playwright install chromium`."
            )
        click.echo(f"Chromium: installed ({executable.name})")
    except ImportError:
        click.echo("Playwright package: MISSING")
        raise click.ClickException("Install the project dependencies before launching")
    click.echo("Configuration: OK")


@main.command("sources")
@click.option("--config-dir", type=click.Path(path_type=Path), default=Path("config"))
def sources_command(config_dir: Path) -> None:
    """Show the enabled real-source panel."""
    sources = load_sources(config_dir)
    summary = panel_summary(sources)
    click.echo(json.dumps(summary, indent=2))
    for source in sources:
        click.echo(f"{source.sector:20} {source.name:24} {source.url}")


@main.command("run")
@click.option("--date", "requested_date", default="auto", show_default=True)
@click.option("--config-dir", type=click.Path(path_type=Path), default=Path("config"))
@click.option("--archive-root", type=click.Path(path_type=Path), default=Path("archive"))
@click.option("--work-root", type=click.Path(path_type=Path), default=Path(".work"))
@click.option("--site-root", type=click.Path(path_type=Path), default=Path("site"))
@click.option("--max-sources", type=int, default=0, help="Balanced live smoke-run limit; 0 uses the full panel.")
@click.option("--force", is_flag=True, help="Intentionally rebuild an existing archive date.")
@click.option("--reuse-capture", is_flag=True, help="Analyze an existing real capture without visiting sites again.")
def run_command(
    requested_date: str,
    config_dir: Path,
    archive_root: Path,
    work_root: Path,
    site_root: Path,
    max_sources: int,
    force: bool,
    reuse_capture: bool,
) -> None:
    """Capture the real panel, calculate a winner, and build the daily package."""
    result = run_daily(
        requested_date=requested_date,
        config_dir=config_dir,
        archive_root=archive_root,
        work_root=work_root,
        site_root=site_root,
        max_sources=max_sources,
        force=force,
        reuse_capture=reuse_capture,
    )
    click.echo(json.dumps(result.to_dict(), indent=2))
    if result.status == "review_only":
        click.echo(
            "CALIBRATION: Result created for internal review. It is not eligible for public posting.",
            err=True,
        )
    elif result.status == "blocked":
        click.echo(
            "BLOCKED: No public result was created. Review the quality-gate reasons and private evidence.",
            err=True,
        )


@main.command("build-site")
@click.option("--config-dir", type=click.Path(path_type=Path), default=Path("config"))
@click.option("--archive-root", type=click.Path(path_type=Path), default=Path("archive"))
@click.option("--site-root", type=click.Path(path_type=Path), default=Path("site"))
def build_site_command(config_dir: Path, archive_root: Path, site_root: Path) -> None:
    """Rebuild the public static archive from approved live results."""
    build_site(archive_root, site_root, load_sources(config_dir))
    click.echo(f"Built {site_root}")


@main.command("year-end")
@click.option("--year", type=int, required=True)
@click.option("--config-dir", type=click.Path(path_type=Path), default=Path("config"))
@click.option("--archive-root", type=click.Path(path_type=Path), default=Path("archive"))
@click.option("--site-root", type=click.Path(path_type=Path), default=Path("site"))
def year_end_command(
    year: int,
    config_dir: Path,
    archive_root: Path,
    site_root: Path,
) -> None:
    """Build the year-in-color summary from approved daily results."""
    settings = load_settings(config_dir)
    sources = load_sources(config_dir)
    try:
        output = write_annual_package(
            archive_root=archive_root,
            year=year,
            sources=sources,
            distance_threshold=settings.recurrence_distance,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    build_site(archive_root, site_root, sources)
    click.echo(f"Built annual package: {output}")


@main.command("publish")
@click.option("--platform", type=click.Choice(["instagram", "bluesky"]), required=True)
@click.option("--date", "requested_date", default="latest", show_default=True)
@click.option("--archive-root", type=click.Path(path_type=Path), default=Path("archive"))
@click.option("--approve", is_flag=True, help="Confirm that a human reviewed this package.")
@click.option("--include-stories", is_flag=True, help="Instagram only: publish the generated Story cards.")
def publish_command(
    platform: str,
    requested_date: str,
    archive_root: Path,
    approve: bool,
    include_stories: bool,
) -> None:
    """Publish an approved, quality-gated package using account credentials."""
    try:
        if platform == "instagram":
            output = publish_instagram(
                archive_root,
                requested_date,
                approved=approve,
                include_stories=include_stories,
            )
        else:
            output = publish_bluesky(
                archive_root,
                requested_date,
                approved=approve,
            )
    except PublishError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Published successfully. Receipt: {output}")


if __name__ == "__main__":
    main()
