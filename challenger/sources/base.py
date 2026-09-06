from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from challenger.models import EvidenceRegion, SourceSpec


@dataclass(slots=True)
class CollectionResult:
    source: SourceSpec
    regions: list[EvidenceRegion] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    def __init__(self, workdir: str | Path, settings: dict):
        self.workdir = Path(workdir)
        self.settings = settings

    @abstractmethod
    def collect(self, source: SourceSpec, run_date: str) -> CollectionResult:
        raise NotImplementedError
