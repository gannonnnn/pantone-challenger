from copy import deepcopy
from dataclasses import replace
import json

import pytest

from challenger.capture.temporal import (
    full_date,
    inspect_dates,
    ranked_snapshot,
    snapshot_is_current,
)
from challenger.config import load_sources, load_settings
from challenger.evidence import prepare_evidence
from challenger.models import SignalStage, PublicationState
from challenger.pipeline import DailyPipeline, stage_diagnostics
from challenger.quality import decide_state
from challenger.sources.base import CollectionResult
from tests.helpers import observation
from tests.test_runtime import _source

URL = "https://music.apple.com/us/new/top-charts"
STAMP = "2026-09-17T01:00:00+00:00"  # September 16 in New York
POLICY = {
    "mode": "ranked_snapshot",
    "urls": [URL],
    "title_words": ["top", "chart"],
    "item_path_prefixes": ["/us/music-video/"],
}


def chart_markup():
    # Reduced structure of the chart's artwork/title/rank association.
    return (
        "<section>"
        + "".join(
            f'<div class="vertical-video"><div class="artwork-wrapper"><a href="/us/music-video/item-{i}/{i}"><img src="{i}.jpg"></a></div>'
            f'<div class="info"><span>{i}</span><span>Video {i}</span><span>Artist</span></div></div>'
            for i in range(1, 4)
        )
        + "</section>"
    )


def chart_proof():
    return ranked_snapshot(chart_markup(), URL, "Top Music Charts", POLICY, STAMP)


@pytest.mark.parametrize("value", ["2026", "2026-09", "2026-02-30", "September 2026"])
def test_partial_or_invalid_dates_are_not_invented(value):
    assert full_date(value) == ""


def test_one_item_date_is_preserved_but_multi_item_dates_are_not_inherited():
    card = (
        '<article><a href="/work/one"><img></a><time datetime="2026-09-16">Sep 16</time></article>'
    )
    assert inspect_dates(card, "https://example.test/work")["published_at"] == "2026-09-16"
    mixed = card + '<article><a href="/work/two"><img></a></article>'
    assert inspect_dates(mixed, "https://example.test/work")["date_status"] == "multiple_items"


def test_modified_dates_and_unrelated_detail_dates_do_not_become_publication():
    html = '<meta property="article:modified_time" content="2026-09-16"><article><time class="updated" datetime="2026-09-16">September 16, 2026</time></article>'
    assert not inspect_dates(html, "https://example.test/a", detail=True)["published_at"]
    html = '<article>Undated work</article><footer><time datetime="2026-09-16">September 16, 2026</time></footer>'
    assert not inspect_dates(html, "https://example.test/a", detail=True)["published_at"]


def test_detail_publication_meta_and_matching_jsonld():
    meta = '<meta property="article:published_time" content="2026-09-16T09:20:00Z">'
    assert (
        inspect_dates(meta, "https://example.test/a", detail=True)["published_at"] == "2026-09-16"
    )

    def ld(url):
        return (
            '<script type="application/ld+json">'
            + json.dumps({"@type": "Article", "url": url, "datePublished": "2026-09-16"})
            + "</script>"
        )

    assert not inspect_dates(ld("https://example.test/b"), "https://example.test/a", detail=True)[
        "published_at"
    ]
    assert (
        inspect_dates(ld("https://example.test/a"), "https://example.test/a", detail=True)[
            "published_at"
        ]
        == "2026-09-16"
    )


def test_exhibition_range_keeps_start_and_end_separate():
    proof = inspect_dates(
        "<article>Apr 23–Nov 1, 2026</article>",
        "https://example.test/show",
        event_type="newly_exhibited",
    )
    assert proof["published_at"] == "2026-04-23"
    assert proof["event_end"] == "2026-11-01"
    assert not inspect_dates(
        "<article>Dec 1–Jan 5, 2026</article>",
        "https://example.test/show",
        event_type="newly_exhibited",
    )["published_at"]
    assert not inspect_dates(
        "<article>Collection 1880–1950</article>",
        "https://example.test/show",
        event_type="newly_exhibited",
    )["published_at"]


def test_exhibition_window_and_ended_event_admission(tmp_path):
    obs = replace(observation(tmp_path, "show", "#A5C84A"), event_type="newly_exhibited")
    obs.region.published_at = "2026-09-01"
    obs.region.metadata["temporal_evidence"] = {"event_end": "2026-11-01"}
    assert len(prepare_evidence([obs], "2026-09-16", {}, tmp_path / "archive")[1]) == 1
    obs.region.metadata["temporal_evidence"]["event_end"] = "2026-09-12"
    assert not prepare_evidence([obs], "2026-09-16", {}, tmp_path / "archive")[0]


def test_chart_is_an_observation_not_a_release_date():
    proof = chart_proof()
    assert proof and proof["published_at"] == "" and len(proof["items"]) == 3
    assert snapshot_is_current(proof, POLICY, URL, STAMP, "2026-09-16", "America/New_York")
    assert not snapshot_is_current(proof, POLICY, URL, STAMP, "2026-09-17", "America/New_York")


@pytest.mark.parametrize(
    "change",
    ["no_policy", "wrong_url", "no_title", "no_ranks", "no_images", "duplicate_rank", "one_item"],
)
def test_generic_or_unverified_chart_regions_do_not_qualify(change):
    html, url, title, policy = chart_markup(), URL, "Top Music Charts", POLICY
    if change == "no_policy":
        policy = {}
    if change == "wrong_url":
        url = "https://music.apple.com/us/new"
    if change == "no_title":
        title = "Music recommendations"
    if change == "no_ranks":
        html = html.replace("<span>1</span>", "<span>Featured</span>")
    if change == "no_images":
        html = html.replace("<img ", "<div ")
    if change == "duplicate_rank":
        html = html.replace("<span>2</span>", "<span>1</span>")
    if change == "one_item":
        html = html.replace("item-2/2", "item-1/1").replace("item-3/3", "item-1/1")
    assert ranked_snapshot(html, url, title, policy, STAMP) is None


def test_tampered_or_old_chart_proof_cannot_qualify(tmp_path):
    for field, value in [
        ("observed_at", "2026-09-15T00:00:00Z"),
        ("html_sha256", ""),
        ("items", [{"url": URL, "rank": 1}] * 3),
    ]:
        proof = deepcopy(chart_proof())
        proof[field] = value
        assert not snapshot_is_current(proof, POLICY, URL, STAMP, "2026-09-16", "America/New_York")
    proof = deepcopy(chart_proof())
    proof["items"][0]["url"] = "https://elsewhere.test/work"
    assert not snapshot_is_current(proof, POLICY, URL, STAMP, "2026-09-16", "America/New_York")


def test_chart_admission_keeps_source_identity_and_future_rejections(tmp_path):
    obs = replace(
        observation(tmp_path, "apple", "#A5C84A", stage=SignalStage.ATTENTION),
        event_type="commercial_attention",
    )
    obs.region.page_url = URL
    obs.region.captured_at = STAMP
    obs.region.metadata["temporal_evidence"] = chart_proof()
    obs.metadata["temporal_policy"] = POLICY
    baseline, current, report, _ = prepare_evidence([obs], "2026-09-16", {}, tmp_path / "archive")
    assert len(baseline) == len(current) == 1
    assert current[0].source_id == obs.source_id  # Three ranks still represent one source group.
    assert report["temporal_counts"] == {"eligible_observed_attention": 1}
    obs.region.published_at = "2026-09-20"
    baseline, current, report, _ = prepare_evidence([obs], "2026-09-16", {}, tmp_path / "archive")
    assert not baseline and not current and report["temporal_counts"] == {"rejected_future": 1}


def test_chart_is_sampled_each_day_within_the_existing_panel(tmp_path):
    pipeline = DailyPipeline(archive_dir=tmp_path / "archive", work_dir=tmp_path / "work")
    for day in range(1, 29):
        active, _ = pipeline._select_sources(f"2026-09-{day:02}", 0)
        assert len(active) == 58
        assert sum(s.panel_type.value == "discovery" for s in active) == 18
        assert "apple-music-charts" in {s.id for s in active}


def test_one_stage_still_blocks_and_no_history_cannot_be_ready():
    args = dict(
        active_sources=58,
        attempted_sources=58,
        captured_sources=35,
        evidence_sources=24,
        domains=8,
        stages=1,
        challenger=[],
        observations=[],
        baseline_days=0,
        settings=load_settings(),
    )
    assert decide_state(**args)[0] == PublicationState.BLOCKED
    args["stages"] = 2
    assert decide_state(**args)[0] == PublicationState.REVIEW_ONLY


def test_stage_report_counts_sources_instead_of_regions():
    source = _source("one")
    results = [
        CollectionResult(source=source, regions=[object(), object()]),
        CollectionResult(source=_source("failed"), report={"status": "error"}),
    ]
    d = {
        "source_id": "one",
        "registry_source_id": "one",
        "baseline_eligible": False,
        "current_eligible": False,
        "temporal_status": "context_only_undated",
    }
    report = stage_diagnostics(results, {"decisions": [d, d]})["creation"]
    assert report["attempted_sources"] == 2 and report["captured_sources"] == 1
    assert report["admitted_sources"] == 0 and report["undated_sources"] == ["one"]
    assert report["collection_failures"] == [{"source_id": "failed", "status": "error"}]


def test_musicbrainz_rejects_partial_dates_before_downloading(tmp_path, monkeypatch):
    from challenger.sources import musicbrainz as module
    from types import SimpleNamespace

    source = next(s for s in load_sources()[1] if s.id == "musicbrainz-new-albums")
    dates = ["2026", "2026-09", "2026-09-01", "2026-09-20", "2026-09-16"]
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "release-groups": [{"id": str(i), "first-release-date": d} for i, d in enumerate(dates)]
        },
    )

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            return response

    downloaded = []

    def download(client, url, path, **kwargs):
        downloaded.append(url)
        return False, "test stops at download boundary"

    monkeypatch.setattr(module.httpx, "Client", Client)
    monkeypatch.setattr(module, "download_item_image", download)
    result = module.MusicBrainzAdapter(tmp_path, {}).collect(source, "2026-09-16")
    assert len(result.report["date_rejections"]) == 4
    assert downloaded == ["https://coverartarchive.org/release-group/4/front-500"]
