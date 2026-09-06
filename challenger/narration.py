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
            f"Yesterday's Challenger: {names} ({values}). "
            f"The signal emerged across {domains}. "
            "Selected by reproducible measurements; narration did not influence the ranking."
        )
