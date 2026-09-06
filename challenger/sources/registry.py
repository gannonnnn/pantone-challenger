from __future__ import annotations

from challenger.sources.artic import ArtInstituteChicagoAdapter
from challenger.sources.base import SourceAdapter
from challenger.sources.cleveland import ClevelandAdapter
from challenger.sources.ebay import EbayBrowseAdapter
from challenger.sources.etsy import EtsyAdapter
from challenger.sources.itunes import ITunesSearchAdapter
from challenger.sources.met import MetAdapter
from challenger.sources.musicbrainz import MusicBrainzAdapter
from challenger.sources.producthunt import ProductHuntAdapter
from challenger.sources.rss import RSSAdapter
from challenger.sources.submissions import SubmissionInboxAdapter
from challenger.sources.webpage import WebpageAdapter


ADAPTERS: dict[str, type[SourceAdapter]] = {
    "webpage": WebpageAdapter,
    "rss": RSSAdapter,
    "met_open_access": MetAdapter,
    "artic_open_access": ArtInstituteChicagoAdapter,
    "cleveland_open_access": ClevelandAdapter,
    "itunes_search": ITunesSearchAdapter,
    "musicbrainz_cover_art": MusicBrainzAdapter,
    "etsy": EtsyAdapter,
    "ebay": EbayBrowseAdapter,
    "product_hunt": ProductHuntAdapter,
    "submission_inbox": SubmissionInboxAdapter,
}


def build_adapter(name: str, workdir, settings) -> SourceAdapter:
    try:
        cls = ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown source adapter: {name}") from exc
    return cls(workdir, settings)
