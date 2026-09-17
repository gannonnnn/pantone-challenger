from __future__ import annotations

import json
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceRuntimeEvent:
    source_id: str
    source_name: str
    adapter: str
    status: str
    regions: int
    duration_seconds: float
    completed: int
    total: int
    recorded_at_epoch: float
    error: str = ""


class RuntimeLedger:
    """Write live, durable progress for long-running collection jobs.

    GitHub Actions output can look frozen while browsers wait on slow sites. The
    ledger prints one line per source and mirrors that information to JSONL plus
    an atomically replaced summary file. If a run fails, the partial ledger is
    still useful as an artifact.
    """

    def __init__(self, directory: str | Path, *, total_sources: int):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.progress_path = self.directory / "runtime-progress.jsonl"
        self.summary_path = self.directory / "runtime-summary.json"
        self.failure_path = self.directory / "runtime-failure.json"
        self.total_sources = int(total_sources)
        self.started_monotonic = time.monotonic()
        self.started_epoch = time.time()
        self._lock = threading.Lock()
        self._events: list[SourceRuntimeEvent] = []
        self._phases: dict[str, dict[str, Any]] = {}
        self._write_summary(status="running")

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_monotonic)

    @property
    def completed_sources(self) -> int:
        with self._lock:
            return len(self._events)

    def start_phase(self, name: str) -> None:
        with self._lock:
            self._phases[name] = {
                "started_elapsed_seconds": round(self.elapsed_seconds, 3),
                "status": "running",
            }
            self._write_summary_unlocked(status="running")
        print(f"[phase] {name} started — {format_duration(self.elapsed_seconds)} elapsed", flush=True)

    def end_phase(self, name: str) -> None:
        with self._lock:
            phase = self._phases.setdefault(name, {})
            started = float(phase.get("started_elapsed_seconds", self.elapsed_seconds))
            phase.update(
                status="complete",
                ended_elapsed_seconds=round(self.elapsed_seconds, 3),
                duration_seconds=round(max(0.0, self.elapsed_seconds - started), 3),
            )
            self._write_summary_unlocked(status="running")
        print(f"[phase] {name} complete — {format_duration(self.elapsed_seconds)} elapsed", flush=True)

    def record_source(
        self,
        *,
        source_id: str,
        source_name: str,
        adapter: str,
        status: str,
        regions: int,
        duration_seconds: float,
        error: str = "",
    ) -> None:
        with self._lock:
            if any(event.source_id == source_id for event in self._events):
                return
            event = SourceRuntimeEvent(
                source_id=source_id,
                source_name=source_name,
                adapter=adapter,
                status=status,
                regions=int(regions),
                duration_seconds=round(float(duration_seconds), 3),
                completed=len(self._events) + 1,
                total=self.total_sources,
                recorded_at_epoch=time.time(),
                error=str(error)[:500],
            )
            self._events.append(event)
            with self.progress_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
            self._write_summary_unlocked(status="running")
        name = source_name if len(source_name) <= 32 else source_name[:29] + "..."
        suffix = f" — {error[:120]}" if error else ""
        print(
            f"[{event.completed:02d}/{event.total:02d}] {name} ({adapter}) — "
            f"{status} — {regions} region{'s' if regions != 1 else ''} — "
            f"{duration_seconds:.1f}s{suffix}",
            flush=True,
        )

    def heartbeat(self, *, active: int, pending: int, label: str = "collection") -> None:
        print(
            f"[heartbeat] {label}: {self.completed_sources}/{self.total_sources} complete; "
            f"{active} active; {pending} pending; {format_duration(self.elapsed_seconds)} elapsed",
            flush=True,
        )

    def finalize(self, *, status: str = "complete", extra: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            summary = self._summary_payload(status=status)
            if extra:
                summary.update(extra)
            self._atomic_json(self.summary_path, summary)
        print(
            f"[runtime] {status} — {self.completed_sources}/{self.total_sources} sources — "
            f"{format_duration(self.elapsed_seconds)}",
            flush=True,
        )
        return summary

    def fail(self, exc: BaseException) -> None:
        payload = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "completed_sources": self.completed_sources,
            "total_sources": self.total_sources,
        }
        self._atomic_json(self.failure_path, payload)
        self.finalize(status="failed", extra={"failure": payload})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._summary_payload(status="running")

    def _summary_payload(self, *, status: str) -> dict[str, Any]:
        statuses = Counter(event.status for event in self._events)
        adapters = Counter(event.adapter for event in self._events)
        timed_out = [
            event.source_id
            for event in self._events
            if "timeout" in event.status or "budget" in event.status
        ]
        return {
            "status": status,
            "started_at_epoch": self.started_epoch,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "total_sources": self.total_sources,
            "completed_sources": len(self._events),
            "remaining_sources": max(0, self.total_sources - len(self._events)),
            "status_counts": dict(sorted(statuses.items())),
            "adapter_counts": dict(sorted(adapters.items())),
            "timed_out_sources": timed_out,
            "phases": self._phases,
            "events": [asdict(event) for event in self._events],
        }

    def _write_summary(self, *, status: str) -> None:
        with self._lock:
            self._write_summary_unlocked(status=status)

    def _write_summary_unlocked(self, *, status: str) -> None:
        self._atomic_json(self.summary_path, self._summary_payload(status=status))

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
        temporary.replace(path)


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes:d}m {secs:02d}s"
    return f"{secs:d}s"
