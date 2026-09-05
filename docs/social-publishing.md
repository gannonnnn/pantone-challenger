# Social Publishing Design — Version 1.3

## Current state

Social publishing must remain disabled during V1.3 calibration. The first seven accepted full-panel runs are internal evidence checks, not content for Instagram or Bluesky.

## Approval model after calibration

1. A full-panel run produces a `ready` review package.
2. A human inspects the evidence contact sheet, coverage, swatches, company metadata, and runner-ups.
3. Merging the daily pull request places the approved result on `main`.
4. A manual publisher may then use the approved package.
5. Scheduled publishing may be considered only after a stable manual period.

An unmerged, blocked, or review-only result is not publishable.

## Credentials

Sensitive credentials belong in GitHub Actions **Secrets**, never in workflow files, commits, issues, pull requests, or repository Variables.

Instagram publishing expects:

```text
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
```

Bluesky publishing expects:

```text
BLUESKY_HANDLE
BLUESKY_APP_PASSWORD
```

Non-sensitive settings such as `PUBLIC_BASE_URL`, `META_GRAPH_VERSION`, and `AUTO_PUBLISH` may use repository Variables.

## Duplicate prevention

The publisher creates a durable reservation tag before calling a social API. If a lock exists without a completion tag, automation stops rather than blindly retrying. A human must inspect the social account before forcing a retry.

## Recommended rollout

- Calibration: no social posting.
- First 7–14 public days: manual posting only.
- After a stable manual period: test one manual workflow publish.
- Later: consider scheduled feed publishing while keeping daily merge approval human-controlled.
- Stories should remain manual until separately tested.
