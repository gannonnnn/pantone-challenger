# Install and run Pantone Challenger v1.6.0

This revised installer was matched to your uploaded `pantone-challenger-current.zip` on September 17, 2026. That project identifies itself as v1.5.2; this package includes the missing v1.5.3 runtime repair as well as the v1.6 improvements. It has not been pushed to your GitHub repository or deployed. The installer checks the files it needs to change and stops before editing if your current code differs. You do not need to replace your repository or recreate its secrets.

## Resume from where you stopped

1. Download the revised `Pantone-Challenger-v1.6.0-Update.zip` and unzip it.
2. Open the folder named **Pantone-Challenger-Matched-Update**. Use the installer in this newly downloaded folder.
3. In GitHub Desktop, select `pantone-challenger` and choose **Repository → Open in Terminal**.
4. Type `python3` followed by a space. Drag this folder's `install_update.py` into Terminal. Add a space and `--repo .`, including the dot. Press Return.
5. Success says **Update applied on branch: pantone-improvements-v1.6.0**. Return to GitHub Desktop to review the changes, or send a screenshot for the next step.

The detailed instructions below cover committing, testing, collecting the first day, and the optional AI reviewer. You can complete those after the installer succeeds.

## What this update does

- Compares a color within source groups observed on both sides of a historical comparison, using equal domain weights. Additional coverage alone does not become growth.
- Keeps creators, publishers, individual items, and campaigns separate. Unknown creators are conservatively grouped at their publisher; Etsy/eBay seller IDs are retained where available.
- Admits dated and substantive evidence before ranking. Undated benchmark imagery can build a baseline; undated historical art cannot become a current color signal.
- Uses an explicit baseline-admission record and a new compatibility key. Incompatible older observations remain in the archive but do not establish the new baseline.
- Corrects captions and alt text to distinguish winning support from overall coverage. Non-ready days produce a review/baseline image rather than a public color package.
- Adds a linked Color Trail to each approved public day. The trail describes observations through that date and links to sources; it does not claim where a color originated.
- Preserves original captured images inside the daily evidence artifact, supports local same-day resume, and preserves the old result when a rebuild fails.
- Gives API collectors hard process deadlines, retaining the existing shared browser, progress messages, and outer job timeout.
- Adds optional AI image annotations, a dry run, cached successful responses, request/time limits, and a human-label evaluation command. AI suggestions do not change rankings or publication.

## 1. Download and unzip the update

Download `Pantone-Challenger-v1.6.0-Update.zip` and double-click it to unzip. Its top-level folder contains:

- `install_update.py`: installer for your existing local Git repository.
- `update.patch` and `update-manifest.json`: the changes and compatibility checks.
- `IMPLEMENTATION.md`: these instructions.
- `VALIDATION.md`: what was tested and what still needs a live run.
- `source/`: the complete updated source for reference or a separate fresh checkout.

Keep these files together. Do not drag the entire `source/` folder over your existing repository.

## 2. Find your local repository folder

If you use GitHub Desktop, select Pantone Challenger, click **Fetch origin**, and pull any existing remote changes you intend to retain. Then choose **Repository → Show in Finder**. The folder should contain `pyproject.toml`, `challenger`, and `config`.

If GitHub Desktop shows local changes, commit them first. The installer deliberately stops for uncommitted work. If you only have the project on GitHub, clone that existing repository through GitHub Desktop first; downloading a source ZIP is not the same as a Git clone.

The installer needs Python 3.9 or newer and Git. Running the application locally needs Python 3.11 or newer. GitHub Actions already uses Python 3.12, so you can let GitHub run the application tests after installation.

## 3. Run the installer

On your Mac, open Terminal. The command is:

```bash
python3 /path/to/unzipped-update/install_update.py --repo /path/to/pantone-challenger
```

You can avoid typing the paths:

1. Type `python3 `, including the trailing space.
2. Drag `install_update.py` from the unzipped update into Terminal.
3. Type ` --repo `, including spaces.
4. Drag your local **repository folder** into Terminal.
5. Press Return.

Success prints the new branch name, normally `pantone-improvements-v1.6.0`. It applies and stages the changes on that branch, leaving your original branch unchanged. It does not commit, push, merge, change your GitHub variables, or publish anything.

If it says **Your version differs**, first check that you ran `install_update.py` from the newly downloaded **Pantone-Challenger-Matched-Update** folder. If you did, your project has changed since the uploaded ZIP; share a fresh export so the change can be reconciled. No files were changed by a failed compatibility check.

## 4. Commit and open the pull request

In GitHub Desktop:

1. Confirm the current branch is the update branch printed by the installer.
2. Review the changed files.
3. Enter a commit summary such as `Improve Pantone Challenger measurement and optional AI review`.
4. Click **Commit to [the update branch]**.
5. Click **Publish branch**.
6. Click **Create Pull Request** and open it on GitHub.
7. Wait for **CI** to pass. The full automated test suite, Python lint, temporal validation, runtime validation, and source validation run there.

The installer also prints exact Terminal commands if you prefer them. Your repository identity, existing history, API secrets, and Pages settings are retained.

## 5. Keep the first collection manual

Before merging, inspect **Settings → Secrets and variables → Actions → Variables**. For the first calibration run, set `ENABLE_DAILY_SCHEDULE` to `false` if it is currently `true`, and keep social publishing disabled. This prevents an existing schedule from immediately using the new methodology before you review it.

Once CI passes and you are ready to install, merge the update pull request. Then open:

**Actions → Daily Challenger → Run workflow**

Use:

| Input | Value |
| --- | --- |
| Branch | `main` |
| `date` | `auto` |
| `max_sources` | `0` |
| `rebuild` | unchecked / `false` |

**Date change:** `auto` now means today's observation date in `America/New_York`. It previously meant yesterday, even though the workflow fetched live pages at run time. A live screenshot does not establish what the page showed yesterday. You can post the completed snapshot the next day as yesterday's report, retaining the original observation date. Dated feed items still use their documented current-event windows. Live backdating is rejected.

A full run selects the fixed benchmark plus rotating discovery sources. Small `max_sources` values are diagnostic only and cannot establish full-panel validity. Source failures remain visible and may correctly block publication.

## 6. Read the result

Open the run and its summary. During browser collection, source-level progress and periodic heartbeats should appear. The command is bounded to 28 minutes and the job to 35 minutes, excluding queue time; these are limits, not runtime promises.

At the bottom of the completed Actions run, inspect the available artifacts:

- `private-evidence-YYYY-MM-DD`: source reports, runtime progress, original images, and contact/proof sheets.
- `daily-package-YYYY-MM-DD`: the result, evidence-admission report, baseline ledger, manifest, captions, and appropriate review or public images.
- `failed-run-diagnostics-YYYY-MM-DD`: available diagnostic files when the command fails.

The publication states mean:

| State | What to do |
| --- | --- |
| `review_only` | Review a valid calibration day. It can build history but has no public color package. |
| `baseline_only` | Valid observations were collected, but no emerging candidate qualified. Retain the baseline after review. |
| `blocked` | Inspect the failure reasons. Do not add this day to valid history or post its provisional findings. |
| `ready` | Review the color, counts, dates, and sources before merging the daily result and publishing. |

A green Actions run means the software completed; a blocked or baseline-only result can still be the correct outcome.

## 7. Build the new baseline

The compatibility key changed to `cohort-evidence-v2`. The older archive remains available, but its observations do not establish the new baseline or the new methodology's recurrence counts.

Collect at least seven distinct valid days. **Merge valid calibration/baseline-only daily pull requests after checking their summaries.** The next Actions run checks out the archive on `main`; unmerged daily branches are not part of that history. Merging a baseline-only day records observations but does not create a public winner. The generated website only includes ready days.

Public growth requires enough source-level overlap as well as calendar history: by default, five prior observations per source, five comparable dates, at least six shared benchmark groups, and at least 50% of currently observed benchmark groups within each accepted comparison. No upward change means no emerging Challenger, regardless of how many new discovery items were collected.

After dependable calibration and review, set `ENABLE_DAILY_SCHEDULE` to `true` to resume scheduled collection. The existing review-before-publication process remains.

## 8. Use the optional AI image reviewer

The AI reviewer is a separate manual workflow. It examines already captured image copies; it does not recollect sources, change a winner, or publish. Its integration uses the OpenAI Responses API and structured output. No paid API call was made during this update's validation.

### Start with a dry run

1. Open a successful **Daily Challenger** run created by v1.6.0.
2. Copy its numeric run ID from the end of its Actions URL and note the observation date.
3. Open **Actions → AI Image Review (optional) → Run workflow**.
4. Enter that `run_id` and `date`; leave `max_images` at `12`.
5. Leave `execute` unchecked. Run it.
6. Download `ai-review-YYYY-MM-DD` and inspect `ai-review.json`. It should list `would_review` rows and zero requests. Original images stay in the daily evidence artifact.

### Activate a small shadow review

1. Create an OpenAI API key in your API account, if needed. This feature requires a separately configured key, and [API usage is billed separately from ChatGPT](https://help.openai.com/en/articles/9039756-billing-settings-in-chatgpt-vs-platform).
2. In your GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it `OPENAI_API_KEY` and paste the key into the secret value. Never put the key into a source file or commit it.
4. Rerun **AI Image Review (optional)** with `execute` checked and `max_images: 12`.
5. The default model is `gpt-4.1-mini`; choose another image-capable Responses model with structured-output support if your account requires it.
6. Review the suggested content type, color role, decision, reason, and optional region. Treat the result as an annotation, not measured truth. Missing keys, refusals, invalid responses, and timeouts remain visible review-needed states.

The command allows at most 50 selected images, runs requests sequentially within a 180-second processing budget, makes no automatic retries, and caps output tokens per request. It records usage returned by the API. Set any additional spending limits in your API account; the image/time limits are not a dollar-denominated budget.

Successful annotations are cached in `.work/ai-cache` for local repeated reviews. Each fresh GitHub runner starts without that cache; repeating a live AI workflow can incur new requests. The cache key includes the image hash, model, prompt, and schema. AI remains in shadow mode in this release: there is no switch that lets its annotations alter rankings.

### Evaluate the reviewer

The review artifact also contains `human-labels-template.csv`. Label `expected_decision` as `accept`, `reject`, or `review`; label held-out rows with `split=test`. Keep examples from the same creator/campaign together when constructing your development and held-out sets.

Locally, run:

```bash
challenger evaluate-ai path/to/ai-review.json path/to/labelled-images.csv
```

This reports precision, recall, accuracy, and missing predictions for the labelled test rows. It does not establish general accuracy from a small sample. Evaluate real images across your domains before designing any future automatic filtering.

## 9. Check source activation

The update preserves your existing source registry. In the reviewed snapshot, Etsy, eBay, Product Hunt, and the community submission inbox were disabled. Your live registry may have changed.

Locally run:

```bash
challenger sources
```

It distinguishes disabled sources, missing credentials, selected sources, and enabled sources that are rotating out that day. It prints secret names, never secret values.

To activate an existing adapter, first configure its named repository secret and then change that source's `enabled` field in `config/sources.yml` on a separate branch. Review and test one activation at a time. A configured discovery source may not be selected every day. Verify original item dates and substantive imagery; a Product Hunt thumbnail can be only a logo. The Product Hunt API also has commercial-use restrictions described in its official documentation.

## 10. Local resume and recovery

If you want to run commands on your Mac rather than GitHub Actions, first open Terminal in your repository and install the application:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Use Python 3.11 or newer. Keep `.venv` out of Git; the existing ignore file already excludes it. Activate it again with `source .venv/bin/activate` when opening a new Terminal session. Optional API source credentials must also be configured in that local environment; GitHub secrets are only available on GitHub runners.

For a local same-day run whose successful captures remain in the same working directory:

```bash
challenger run --date auto --resume
```

If that date already has an archive result and you deliberately want to replace it after validation:

```bash
challenger run --date auto --resume --rebuild
```

Resume checks the selected sources/settings and image checksums, reuses successful intact captures, and retries failed sources. It is not a general historical replay command. On a fresh GitHub runner the previous `.work` tree is absent; the daily workflow does not automatically restore an earlier run for resume. Rebuild preserves the existing archive if the replacement fails.

If you need to undo the installation before committing, use GitHub Desktop to review/discard only the update changes and switch back to your original branch. If it was already merged, use GitHub's revert flow for the update pull request; keep observation histories and distinguish their methodology versions.

## What still needs live validation

The automated tests exercise the data pipeline with controlled evidence, hard timeouts, rendering, resume, frozen-result checks, and mocked API responses. A full collection on your GitHub runner and a real API review using your account are still required. Website availability, authentication, anti-bot behavior, and model quality cannot be established by unit tests.

The first public release may take more than seven days if coverage or comparable observations are insufficient. The system will explain why instead of forcing a color.

## Official references

- [GitHub: manually run a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [OpenAI: images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [OpenAI: structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI: GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [Product Hunt API](https://api.producthunt.com/v2/docs)
