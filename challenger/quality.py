from __future__ import annotations

from challenger.models import PublicationState


def decide_state(
    *,
    active_sources: int,
    attempted_sources: int,
    captured_sources: int,
    evidence_sources: int,
    domains: int,
    stages: int,
    challenger: list,
    observations: list,
    baseline_days: int,
    settings: dict,
):
    q = settings.get("quality", {})
    blocking = []
    review = []
    min_evidence_block = max(int(q.get("min_evidence_sources_block", 8)), int(active_sources * float(q.get("min_coverage_block", 0.30))))
    min_evidence_ready = max(int(q.get("min_evidence_sources_ready", 18)), int(active_sources * float(q.get("min_coverage_ready", 0.55))))
    if evidence_sources < min_evidence_block:
        blocking.append(
            f"Only {evidence_sources} of {active_sources} active sources produced eligible creative evidence; at least {min_evidence_block} are required for a valid baseline day."
        )
    if domains < int(q.get("min_domains_block", 4)):
        blocking.append(f"Only {domains} domains produced evidence; at least {q.get('min_domains_block', 4)} are required.")
    if stages < int(q.get("min_stages_block", 2)):
        blocking.append(f"Only {stages} signal stages produced evidence; at least {q.get('min_stages_block', 2)} are required.")
    if blocking:
        return PublicationState.BLOCKED, blocking, review

    if evidence_sources < min_evidence_ready:
        review.append(
            f"Coverage is sufficient for baseline learning but not public publication: {evidence_sources}/{active_sources} sources versus a ready threshold of {min_evidence_ready}."
        )
    if domains < int(q.get("min_domains_ready", 6)):
        review.append(f"Only {domains} domains were covered; public-ready target is {q.get('min_domains_ready', 6)}.")
    if stages < int(q.get("min_stages_ready", 3)):
        review.append(f"Only {stages} signal stages were covered; public-ready target is {q.get('min_stages_ready', 3)}.")
    calibration_days = int(settings.get("baseline", {}).get("calibration_days", 7))
    if baseline_days < calibration_days:
        review.append(f"Historical baseline is warming: {baseline_days}/{calibration_days} prior valid days.")
    if not challenger:
        if baseline_days >= calibration_days:
            return PublicationState.BASELINE_ONLY, [], review + ["No candidate passed the emergence and convergence gates today."]
        return PublicationState.REVIEW_ONLY, [], review + ["No public Challenger is selected during calibration."]
    for candidate in challenger:
        if candidate.score_margin < float(q.get("min_score_margin", 3.0)) and len(challenger) == 1:
            review.append("The leading score is close to the next candidate; treat as review-only unless a tie is selected.")
    return (PublicationState.REVIEW_ONLY if review else PublicationState.READY), [], review
