"""Narration boundary: measurements choose; narration explains.

The default implementation is deterministic and offline. A future provider may implement
`Narrator` only after the measured result has been frozen. Narration output is never fed
back into scoring, ties, recurrence, or publication state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NarrativeContext:
    date: str
    color_names: tuple[str, ...]
    hex_values: tuple[str, ...]
    domains: tuple[str, ...]
    stages: tuple[str, ...]
    state: str


class Narrator(Protocol):
    def caption(self, context: NarrativeContext) -> str: ...


class TemplateNarrator:
    def caption(self, context: NarrativeContext) -> str:
        names = " + ".join(context.color_names)
        values = " + ".join(context.hex_values)
        domains = ", ".join(context.domains[:4]) or "the monitored cultural panel"
        return (
            f"Challenger observed {context.date}: {names} ({values}). "
            f"Supporting evidence appeared across {domains}. "
            "Selected by reproducible measurements; narration did not influence the ranking."
        )


def explain_candidate(candidate) -> str:
    comparison = candidate.comparison or {}
    if not comparison.get("valid"):
        return "Not enough comparable source history to establish growth. Newly observed does not mean newly popular."
    pairs = comparison.get("pairs", [])
    size = min((p["cohort_size"] for p in pairs), default=0)
    change = comparison.get("change_percentage_points", 0)
    return (f"Comparable benchmark prevalence changed by {change:+.1f} percentage points "
            f"across {comparison.get('comparable_days', 0)} paired dates "
            f"(at least {size} shared source groups per pair; equal domain weighting). "
            "Discovery evidence is shown separately and does not enlarge this comparison.")
