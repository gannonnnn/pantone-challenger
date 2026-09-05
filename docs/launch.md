# Pantone Challenger V1.3 — Simple Repair and Calibration Steps

V1.3 is a safety repair. It removes the unreliable logo treatment, requires a real local color match from a sampled marketing-creative region, and keeps the first seven accepted runs private.

## Part 1 — Put the repair into GitHub

1. Download the V1.3 upgrade ZIP and double-click it.
2. Open GitHub Desktop.
3. Choose the `pantone-challenger` repository.
4. Switch **Current Branch** to `main`.
5. Click **Fetch origin**. Click **Pull origin** if it appears.
6. Stop unless GitHub Desktop says **No local changes**.
7. Open Terminal.
8. Type `bash `, including the space.
9. Drag `APPLY-PANTONE-CHALLENGER-V1.3.sh` from Finder into Terminal.
10. Press Return.
11. When the folder chooser opens, use GitHub Desktop → **Repository → Show in Finder**. Select that exact `pantone-challenger` folder.
12. The updater creates a safe branch named `v1-3-repair` and copies the repaired files there.
13. Return to GitHub Desktop and use this summary:

```text
fix: rebuild evidence integrity and calibration
```

14. Click **Commit to v1-3-repair**.
15. Click **Publish branch** or **Push origin**.
16. Click **Create Pull Request**.
17. Wait for the newest CI check to turn green before merging.

Do not upload the ZIP itself to GitHub. Do not apply the repair to a `daily/...` branch.

## Part 2 — Merge the repair

When CI is green:

1. Open the V1.3 repair pull request.
2. Confirm the changed files are the repair—not a daily color result.
3. Click **Merge pull request**.
4. Return to GitHub Desktop.
5. Switch to `main`.
6. Click **Fetch origin**, then **Pull origin** if offered.

Keep **Daily Challenger** disabled or manual-only.

## Part 3 — Run one private calibration day

1. Open GitHub → **Actions → Daily Challenger**.
2. Click **Run workflow**.
3. Use:

```text
Marketing date: auto
Maximum sources: 0
Rebuild an existing date: unchecked
```

4. Wait for the run to finish.
5. Open the new pull request titled **INTERNAL CALIBRATION — DO NOT POST**.
6. Download the private evidence artifact and open the evidence contact sheet.

A run may be:

- `blocked` — no result was trustworthy enough;
- `review_only` — an internal calibration result was created;
- `ready` — public-ready after calibration and stronger gates.

A blocked day is not a failure. It means the product refused to invent a result.

## Part 4 — Review the calibration result

Check only these five things:

1. Does the large color match the printed HEX?
2. Does every company have its own local matching swatch?
3. Are the company name and sector correct?
4. Does the private creative-region image really contain that color?
5. Are the coverage and company counts believable?

V1.3 uses company names instead of unreliable favicons. Logos may be added later only after each one is manually approved.

If the evidence is credible, merge the calibration pull request. It warms the private baseline but does not count toward the public recurrence counter or year-end summary.

## Part 5 — Repeat for seven days

Run one manual full-panel calibration on seven separate days. Do not publish the cards during this period.

After seven good runs, review the method before enabling a schedule or social posting.

## Do not do these things

- Do not rerun or restore the flawed August 30 result.
- Do not force a winner when the product says `blocked`.
- Do not use favicons as logos.
- Do not enable automatic Instagram or Bluesky posting during calibration.
- Do not merge a result only because the card looks attractive.
