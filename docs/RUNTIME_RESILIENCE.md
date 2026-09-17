# Runtime Resilience — V1.5.3

Pantone Challenger measures a broad cultural panel. A single slow website must not be able to turn one daily run into an hour-long opaque job.

## Runtime controls

V1.5.3 adds four layers of protection:

1. **One shared Chromium process.** Webpage sources receive isolated browser contexts, but they no longer launch a fresh browser for every company or cultural source.
2. **Per-source wall-clock budgets.** A webpage receives 55 seconds total, including one optional fallback URL. API and feed adapters receive 45 seconds total, with individual requests capped at 12 seconds.
3. **A graceful collection budget.** Browser collection is capped at 20 minutes. Sources that have not started or completed by then are recorded as unavailable; the remaining evidence continues into the ordinary quality gate.
4. **A 28-minute command backstop plus 35-minute job backstop.** The live measurement command is terminated at 28 minutes if it has not returned, leaving time for GitHub to upload whatever runtime diagnostics exist before the job-level limit is reached.

The configured 58-source daily panel runs with six browser workers. Even if every browser source consumes its full 55-second allowance, the browser waves fit inside the 20-minute collection budget.

## Progress and diagnostics

The live GitHub log now prints one line per source:

```text
[17/58] Spotify (webpage) — captured — 2 regions — 11.4s
[18/58] Etsy (webpage) — source_timeout — 0 regions — 55.0s
```

A heartbeat appears when no source has completed for 20 seconds.

Every run writes:

- `runtime-progress.jsonl` — append-only source completion events;
- `runtime-summary.json` — atomically updated status, phase timing, timeouts, and counts;
- `runtime-failure.json` — the exception and completed-source count when a technical failure occurs.

If the measurement command fails, GitHub uploads the partial runtime folder before marking the job failed. A failed source is evidence about source health, not a reason to discard all completed work.

## Browser efficiency

The browser collector now:

- shares one Chromium process across the batch;
- keeps one isolated context per source;
- runs up to six sources concurrently;
- blocks fonts, video/audio media, and common analytics requests;
- scans candidate elements in one browser-side operation instead of hundreds of Python/browser round trips;
- removes heavily overlapping candidate regions before taking screenshots;
- attempts at most six candidate-region screenshots per source;
- stops after three valid regions;
- permits only one fallback URL;
- closes a timed-out source and continues.

These changes do not loosen any color, provenance, temporal, semantic, duplicate, source-balance, or publication gate.

## API and feed limits

RSS is fetched through the bounded HTTP client instead of allowing the feed parser to perform an unbounded network request. Item adapters check their remaining source budget between requests and downloads. Museum, marketplace, music, film, and submission sources preserve partial valid evidence if they reach their deadline.

## Expected behavior

A full live run is still dependent on third-party site behavior and GitHub runner conditions. V1.5.3 is designed to make the runtime bounded and observable; it cannot guarantee that all sources will respond or that every day will yield a publishable color.

A timed-out or unavailable source is recorded and skipped. The normal evidence-quality rules decide whether the remaining panel is sufficient for `ready`, `review_only`, `baseline_only`, or `blocked`.
