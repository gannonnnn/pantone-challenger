"""Non-browser sources run in killable processes with hard wall-clock budgets."""
from __future__ import annotations

import multiprocessing as mp
import time
from collections import deque
from pathlib import Path

from challenger.sources.base import CollectionResult


def _worker(connection, source, run_date, workdir, settings):
    try:
        from challenger.sources.registry import build_adapter
        result = build_adapter(source.adapter, Path(workdir), settings).collect(source, run_date)
        connection.send(result)
    except BaseException as exc:
        connection.send(CollectionResult(source=source, report={'status': 'adapter_error', 'error': type(exc).__name__}))
    finally:
        connection.close()


def collect_api_sources(sources, run_date, workdir, settings, callback, *, worker=_worker):
    ctx = mp.get_context('spawn')
    capture = settings.get('capture', {})
    workers = max(1, min(6, int(capture.get('api_workers', 3))))
    budget = max(.01, float(capture.get('api_source_timeout_s', 45)))
    pending = deque(sources)
    active = []
    try:
        while pending or active:
            while pending and len(active) < workers:
                source = pending.popleft()
                reader, writer = ctx.Pipe(duplex=False)
                proc = ctx.Process(target=worker, args=(writer, source, run_date, str(workdir), settings))
                proc.start()
                writer.close()
                active.append((proc, reader, source, time.monotonic()))
            for entry in list(active):
                proc, reader, source, started = entry
                elapsed = time.monotonic() - started
                result = None
                if reader.poll():
                    try:
                        result = reader.recv()
                    except EOFError:
                        result = CollectionResult(source=source, report={'status': 'adapter_error'})
                elif elapsed >= budget:
                    result = CollectionResult(source=source, report={'status': 'source_timeout', 'deadline_exceeded': True})
                elif not proc.is_alive():
                    result = CollectionResult(source=source, report={'status': 'adapter_error'})
                if result is not None:
                    if proc.is_alive():
                        proc.terminate()
                    proc.join(timeout=1)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=1)
                    reader.close()
                    active.remove(entry)
                    callback(result, elapsed)
            if active:
                time.sleep(.01)
    finally:
        for proc, reader, _source, _started in active:
            if proc.is_alive():
                proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1)
            reader.close()
