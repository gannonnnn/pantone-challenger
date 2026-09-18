# v1.6.1 validation record

Prepared September 17, 2026, against the installed v1.6.0 matched-update source.

## Original live run

The supplied September 16 artifacts contain 58 attempted sources, 35 sources with captured regions, 109 extracted regions, and 24 admitted source groups. All admitted groups belong to distribution. There are zero prior valid baseline days.

| Stage | Attempted sources | Sources with captured regions | Admitted sources |
| --- | ---: | ---: | ---: |
| Creation | 11 | 6 | 0 |
| Distribution | 42 | 27 | 24 |
| Attention | 5 | 2 | 0 |

The original decisions are 62 calibration-only undated regions, 31 excluded undated regions, eight current regions, and eight stale regions. The program's green workflow status and its blocked publication state are consistent: execution succeeded, but stage coverage failed.

Replay used the original saved dates, source identities, and extracted swatches, with no date backfilling. It reproduced all original temporal-status counts and the same single admitted stage. SHA-256 verification passed for all 109 recorded image files against their saved file hashes. This is a replay of saved extraction, not a second claim of live collection.

Input archive SHA-256 values:

```text
daily-package-2026-09-16.zip
1023846a6b9bf124c7934bf1b450e01fce1b46b5343dd5d00467c5a631d27643

private-evidence-2026-09-16.zip
62b01bcb3381d7130427c27542c83ecaa0dd6070552d33e54cee30b69b768f6b
```

## Automated checks

- Full local suite: **122 passed, two skipped**. Both skips are the new Chromium fixture tests because no Chromium executable is available in this workspace. A bounded browser download attempt timed out. CI and the daily workflow install Chromium and require these tests to run successfully; review their results before merging.
- Critical Python lint: passed. Full lint on the new temporal parser and its test files: passed.
- Temporal-integrity, bounded-runtime, and release/source-registry validation: passed.
- The registry declares 67 enabled sources across 12 domains and all three stages; each complete daily sample remains 40 benchmark plus 18 discovery sources.
- Regression cases cover full versus partial dates, publication versus modification, item/date association, matching detail metadata, exhibition ranges and ended events, chart identity/rank requirements, observation timezone, invalid or stale proof, MusicBrainz download filtering, source-count diagnostics, daily sample limits, future-date rejection, and unchanged publication gates.
- The installer was checked against the exact v1.6.0 baseline: expected v1.6.1 bytes staged on a new branch, original main unchanged, no push or merge. Its mismatch and damaged-package refusal paths are covered by the existing installer tests.

## Real chart structure check

The parser was exercised against freshly fetched HTML from the [official Apple Music charts page](https://music.apple.com/us/new/top-charts). It recognized the four ranked shelves and rejected the two unranked city/global playlist shelves. This verifies current HTML parsing; it is not a new 58-source browser run or historical evidence for September 16.

The saved September 16 chart crop visibly contains ranked music videos. The old collector did not save the DOM associations needed by the new admission rule, so this package does not rewrite that historical result. A fresh run must collect the proof.

## Limits and next checks

This package has not been applied to the user's Mac or pushed to GitHub. Browser fixture results and a fresh full live collection remain to be checked in GitHub Actions. Live sites may refuse requests, change layout, or contain no qualifying current material. The new report makes those failures visible; it does not guarantee a public winner.

The two existing Pillow deprecation warnings did not fail tests. No paid AI requests were made. Optional AI annotations remain separate from date admission, ranking, and publication.
