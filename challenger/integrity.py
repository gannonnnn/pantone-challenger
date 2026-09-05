from __future__ import annotations

from .colors import delta, oklab_from_hex
from .config import Settings
from .models import DailyResult, Source
from .recurrence import color_family_name


class IntegrityError(RuntimeError):
    pass


def validate_result_integrity(
    result: DailyResult,
    sources: list[Source],
    settings: Settings,
) -> None:
    if result.status == "blocked":
        return
    if result.winner is None:
        raise IntegrityError("A non-blocked result has no winner")

    registry = {source.id: source for source in sources}
    candidates = [result.winner, *result.runners_up]
    for candidate in candidates:
        try:
            stored_lab = oklab_from_hex(candidate.hex)
        except ValueError as exc:
            raise IntegrityError(f"Invalid candidate HEX value: {candidate.hex}") from exc
        if delta(stored_lab, candidate.oklab) > 0.012:
            raise IntegrityError(
                f"Candidate {candidate.hex} does not match its stored perceptual color"
            )
        expected_family = color_family_name(candidate.oklab)
        if candidate.family_label != expected_family:
            raise IntegrityError(
                f"Candidate family mismatch: {candidate.family_label!r} != {expected_family!r}"
            )
        seen_sources: set[str] = set()
        for evidence in candidate.evidence:
            source = registry.get(evidence.source_id)
            if source is None:
                raise IntegrityError(
                    f"Candidate evidence references unknown source {evidence.source_id}"
                )
            if evidence.source_id in seen_sources:
                raise IntegrityError(
                    f"Source {evidence.source_id} appears more than once in one candidate"
                )
            seen_sources.add(evidence.source_id)
            if evidence.source_name != source.name:
                raise IntegrityError(
                    f"Source name mismatch for {source.id}: {evidence.source_name!r}"
                )
            if evidence.sector != source.sector:
                raise IntegrityError(
                    f"Sector mismatch for {source.id}: {evidence.sector!r} != {source.sector!r}"
                )
            if not evidence.region_id or not evidence.region_path:
                raise IntegrityError(
                    f"Evidence from {source.id} is missing a traceable region reference"
                )
            if not 0.0 < evidence.local_share <= 1.0:
                raise IntegrityError(
                    f"Invalid local color share for {source.id}: {evidence.local_share}"
                )
            try:
                local_lab = oklab_from_hex(evidence.local_hex)
            except ValueError as exc:
                raise IntegrityError(
                    f"Invalid local evidence HEX for {source.id}: {evidence.local_hex}"
                ) from exc
            if delta(local_lab, evidence.local_oklab) > 0.012:
                raise IntegrityError(
                    f"Local evidence HEX and perceptual color disagree for {source.id}"
                )
            measured = delta(candidate.oklab, evidence.local_oklab)
            if measured > settings.max_evidence_distance + 1e-9:
                raise IntegrityError(
                    f"Evidence from {source.id} is too far from candidate {candidate.hex}"
                )
            if abs(measured - evidence.distance_to_candidate) > 0.002:
                raise IntegrityError(
                    f"Stored evidence distance is inconsistent for {source.id}"
                )
            if evidence.region_confidence < 0 or evidence.region_confidence > 1:
                raise IntegrityError(
                    f"Invalid region confidence for {source.id}: {evidence.region_confidence}"
                )
        if candidate.source_count != len(candidate.evidence):
            raise IntegrityError(
                f"Candidate source count {candidate.source_count} does not match "
                f"{len(candidate.evidence)} traceable evidence records"
            )
        if candidate.source_ids != [item.source_id for item in candidate.evidence]:
            raise IntegrityError("Candidate source arrays do not match evidence order")
        if candidate.source_names != [item.source_name for item in candidate.evidence]:
            raise IntegrityError("Candidate source-name array does not match evidence order")
        if candidate.source_sectors != [item.sector for item in candidate.evidence]:
            raise IntegrityError("Candidate source-sector array does not match evidence order")
        if candidate.max_evidence_distance and abs(
            candidate.max_evidence_distance
            - max((item.distance_to_candidate for item in candidate.evidence), default=0.0)
        ) > 0.002:
            raise IntegrityError("Candidate maximum evidence distance is inconsistent")

    for source_id, relative in result.source_logos.items():
        source = registry.get(source_id)
        if source is None:
            raise IntegrityError(f"Logo map references unknown source {source_id}")
        if source.brand_mark_status != "approved":
            raise IntegrityError(
                f"Unapproved brand mark was included for source {source_id}: {relative}"
            )
