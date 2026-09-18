# Pantone Challenger v1.6.1 repair

Your September 16 workflow finished successfully. The result was blocked because only distribution evidence passed admission. A green workflow check means the program finished; it does not mean a publishable color was found.

## Install on your Mac

1. Download `Pantone-Challenger-v1.6.1-Repair.zip` and double-click it.
2. Move the resulting `Pantone-Challenger-Date-Repair` folder onto your Desktop.
3. In GitHub Desktop, choose `pantone-challenger`, switch **Current Branch** to `main`, click **Fetch origin**, and click **Pull origin** if it appears. This brings in the v1.6.0 update you already merged.
4. Open Terminal. Copy this whole command, paste it, and press Return:

```bash
python3 "$HOME/Desktop/Pantone-Challenger-Date-Repair/install_update.py" --repo "$HOME/Documents/GitHub/pantone-challenger"
```

Success says `Update applied on branch: pantone-improvements-v1.6.1` (a numbered suffix is fine). The command works even if Terminal opens in your home folder. The installer checks the installed v1.6.0 files before changing them and stops if they differ. If it stops, send the message; do not force the patch.

## Save the repair to GitHub

5. Return to GitHub Desktop. Enter **Repair evidence dates** in Summary, then click **Commit to pantone-improvements-v1.6.1**.
6. Click **Publish branch**, then **Create Pull Request**. On GitHub, create the pull request into `main`.
7. Wait for the checks. This version also tests image/date capture in Chromium. When all checks pass, review and merge the repair with **Merge pull request**, then **Confirm merge**.

## Collect a fresh day

8. On GitHub, go to **Actions → Daily Challenger → Run workflow**. Choose branch `main`; leave date as `auto`, max sources as `0`, and rebuild unchecked. Click **Run workflow**.
9. Open that run after it finishes. Read the new **Evidence by stage** table in its summary. `review_only` is an expected calibration result when coverage qualifies but there is not enough history. It is not a color to post. `blocked` means a stated evidence requirement still failed.
10. If GitHub creates a daily calibration pull request, review it and merge it to retain that valid day in `main`. Otherwise the next run cannot use that day as history. Once the collection is working reliably, the existing daily schedule can continue collecting new observations.

The September 16 result remains blocked. New runs cannot recreate the old webpages. If a result already exists for today's date, inspect it before selecting rebuild.

## What was repaired

The webpage collector previously saved an empty publication date for every region. Creation and attention images were then rejected as undated. Some of the captured images also depicted genuinely old or permanent work and should remain excluded.

- Item dates: capture an explicit full date within one item, or from a linked detail page on an allowed host. Modified dates, unrelated listing dates, ambiguous dates, and year-only dates do not become publication dates.
- Chart observations: Apple Music's ranked charts can document attention at capture time. At least three distinct image/item/rank associations, a configured chart URL, and a chart title are required. Capture time must match the run date in the configured timezone. Generic playlist shelves do not qualify. Multiple ranked entries still represent one source group.
- Exhibitions: use the opening date for the existing 45-day new-exhibition window; retain the closing date separately and exclude ended events. Permanent collections do not acquire a new creation date.
- Music releases: request a recent window and reject incomplete dates before spending time downloading images.
- Sampling: Apple Music Charts stays in each discovery sample, within the existing 18 discovery slots. The complete run remains 58 sources.
- Diagnostics: both artifact ZIPs receive `stage-diagnostics.json`; the summary names sources with missing or stale dates. The private artifact also retains the HTML used for each temporal decision, referenced by relative path and checksum.

Minimum stage counts, coverage thresholds, source weighting, color extraction, and emergence requirements are not lowered. Public readiness still requires all three stages and enough compatible history. Live websites may change, deny access, or lack qualifying items; the repair does not guarantee a public winner.

## AI's role

Keep the optional AI image reviewer as an assistant for describing crops and flagging questionable imagery. The color calculation and date admission remain traceable to saved evidence. AI should not guess missing dates or waive a blocked result. The existing AI setup is described in `docs/IMPLEMENT_V1.6.md`; no AI key is needed for this repair.

## Validation

See `docs/VALIDATION_V1.6.1.md` for the evidence replay, automated tests, and remaining live-browser validation.
