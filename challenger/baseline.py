from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from datetime import date
from math import ceil
from pathlib import Path
from typing import Any

from challenger.color import distance, hex_to_oklab


def load_history(archive_dir: str | Path, before_date: str, limit_days: int = 30,
                 *, compatibility_key: str = "") -> list[dict[str, Any]]:
    """Only explicitly admitted observations can advance the historical baseline."""
    root = Path(archive_dir)
    history = []
    if not root.exists():
        return history
    for day_dir in sorted(root.iterdir(), reverse=True):
        if not day_dir.is_dir() or day_dir.name >= before_date:
            continue
        try:
            date.fromisoformat(day_dir.name)
            manifest = json.loads((day_dir / "manifest.json").read_text())
            if manifest.get("baseline_eligible") is not True or manifest.get("state") == "blocked":
                continue
            if compatibility_key and manifest.get("baseline_compatibility_key") != compatibility_key:
                continue
            if manifest.get("schema_version") == 2:
                verification = json.loads((day_dir / "temporal-semantic-integrity.json").read_text())
                if verification.get("passed") is not True:
                    continue
                expected = manifest.get("validated_sha256", {}).get("observations.json")
                if hashlib.sha256((day_dir / "observations.json").read_bytes()).hexdigest() != expected:
                    continue
            payload = json.loads((day_dir / "observations.json").read_text())
            if not isinstance(payload, list):
                continue
            payload = [obs for obs in payload if isinstance(obs, dict)
                       and obs.get("metadata", {}).get("baseline_eligible") is True]
            if not payload:
                continue
        except (ValueError, OSError, TypeError):
            continue
        history.append({"date": day_dir.name, "observations": payload})
        if len(history) >= limit_days:
            break
    return list(reversed(history))


def observation_shares(observations: list[dict], candidate_lab, threshold: float = 0.045) -> dict[str, float]:
    """One best share per observed actor. Unobserved actors are absent, not zero."""
    shares: dict[str, float] = {}
    for obs in observations:
        actor = str(obs.get("source_id", ""))
        if not actor:
            continue
        best = 0.0
        for swatch in obs.get("swatches", []):
            try:
                lab = tuple(swatch.get("oklab") or hex_to_oklab(swatch["hex"]))
                if distance(lab, candidate_lab) <= threshold:
                    best = max(best, float(swatch.get("adjusted_share")
                                          if swatch.get("adjusted_share") is not None
                                          else swatch.get("share", 0.0)))
            except (KeyError, ValueError, TypeError):
                continue
        shares[actor] = max(shares.get(actor, 0.0), best)
    return shares


def source_color_history(history: list[dict], candidate_lab, threshold: float = 0.045) -> dict:
    rows = defaultdict(list)
    for day in history:
        for actor, share in observation_shares(day.get("observations", []), candidate_lab, threshold).items():
            rows[actor].append(share)
    return {actor: {
        "days": float(len(shares)), "present_days": float(sum(s > 0 for s in shares)),
        "frequency": sum(s > 0 for s in shares) / len(shares),
        "mean_share": sum(shares) / len(shares), "last_share": shares[-1],
    } for actor, shares in rows.items()}


def panel_candidate_history(history: list[dict], candidate_lab, threshold: float = 0.045,
                            *, current_observations: list[dict] | None = None,
                            min_source_days: int = 5, min_cohort_sources: int = 6,
                            min_comparable_days: int = 5, min_cohort_coverage: float = 0.5) -> dict:
    """Paired domain-standardized prevalence on the same observed benchmark actors.

    Each date pair uses an intersection. New actors, missing actors and rotating
    discovery items cannot create lift by changing a denominator. Domains receive
    the same weights in the current and prior side of each comparison.
    """
    def benchmark(rows):
        return [o for o in rows if o.get("panel_type") == "benchmark"
                and o.get("metadata", {}).get("baseline_eligible", True)]

    current = benchmark(current_observations or [])
    now = observation_shares(current, candidate_lab, threshold)
    domains = {str(o["source_id"]): str(o.get("domain", "unknown")) for o in current}
    observations_per_actor = defaultdict(int)
    previous = []
    for day in history:
        rows = benchmark(day.get("observations", []))
        past = observation_shares(rows, candidate_lab, threshold)
        old_domains = {str(o["source_id"]): str(o.get("domain", "unknown")) for o in rows}
        previous.append((day["date"], past, old_domains))
        for actor in past:
            observations_per_actor[actor] += 1
    stable = {actor for actor in now if observations_per_actor[actor] >= min_source_days}
    comparisons = []
    for day, past, old_domains in previous:
        common = sorted(a for a in stable & past.keys() if domains[a] == old_domains[a])
        if len(common) < max(min_cohort_sources, ceil(len(now) * min_cohort_coverage)):
            continue
        by_domain = defaultdict(list)
        for actor in common:
            by_domain[domains[actor]].append(actor)
        current_rate = sum(sum(now[a] > 0 for a in actors) / len(actors)
                           for actors in by_domain.values()) / len(by_domain)
        prior_rate = sum(sum(past[a] > 0 for a in actors) / len(actors)
                         for actors in by_domain.values()) / len(by_domain)
        comparisons.append({"date": day, "cohort_size": len(common),
                            "cohort_ids": common, "domains": len(by_domain),
                            "current_matches": sum(now[a] > 0 for a in common),
                            "prior_matches": sum(past[a] > 0 for a in common),
                            "current_prevalence": current_rate, "prior_prevalence": prior_rate})
    current_mean = sum(x["current_prevalence"] for x in comparisons) / len(comparisons) if comparisons else None
    previous_mean = sum(x["prior_prevalence"] for x in comparisons) / len(comparisons) if comparisons else None
    change = current_mean - previous_mean if comparisons else None
    return {
        "valid": len(comparisons) >= min_comparable_days,
        "method": "paired_benchmark_equal_domain_prevalence_v1",
        "comparable_days": len(comparisons), "observed_benchmark_actors": len(now),
        "stable_benchmark_actors": len(stable),
        "current_prevalence": current_mean, "prior_prevalence": previous_mean,
        "change_percentage_points": round(change * 100, 4) if change is not None else None,
        "relative_lift": current_mean / previous_mean if previous_mean else None,
        "pairs": comparisons,
        "note": "Sample prevalence; missing sources excluded in pairs. Not a population estimate.",
    }
