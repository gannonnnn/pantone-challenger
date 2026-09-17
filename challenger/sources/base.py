from __future__ import annotations

import time
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
    """Base class for bounded non-browser source adapters."""

    def __init__(self, workdir: str | Path, settings: dict):
        self.workdir = Path(workdir)
        self.settings = settings
        capture = settings.get("capture", {})
        self.source_timeout_s = float(capture.get("api_source_timeout_s", 45))
        self.http_timeout_s = float(capture.get("http_timeout_s", 12))
        self._started_at = time.monotonic()

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self._started_at)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.source_timeout_s - self.elapsed_seconds)

    def expired(self, reserve_seconds: float = 0.0) -> bool:
        return self.remaining_seconds <= max(0.0, reserve_seconds)

    def request_timeout(self) -> float:
        """Return a bounded timeout for the next network request."""

        return max(1.0, min(self.http_timeout_s, self.remaining_seconds or 1.0))

    def finalize_result(self, result: CollectionResult) -> CollectionResult:
        result.report.setdefault("duration_seconds", round(self.elapsed_seconds, 3))
        if self.expired():
            result.report["deadline_exceeded"] = True
            if result.regions:
                result.report["status"] = "captured_partial_timeout"
            else:
                result.report["status"] = "source_timeout"
        return result

    @abstractmethod
    def collect(self, source: SourceSpec, run_date: str) -> CollectionResult:
        raise NotImplementedError
