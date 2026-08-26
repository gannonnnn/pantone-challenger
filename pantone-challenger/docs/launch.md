# Launch Pantone Challenger

This is the practical launch sequence for the real product. It assumes a Mac, a GitHub account, and no prior command-line experience beyond copying commands.

## What “launched” means

Pantone Challenger is launched when all of the following are true:

1. The repository is stored in your own GitHub account.
2. The full 48-source nightly workflow completes.
3. A daily review pull request is generated.
4. You merge the first result after inspecting it.
5. The public GitHub Pages archive loads.
6. A social account has successfully received one manually approved post.
7. Automatic publishing remains off until at least several good daily runs have been reviewed.

The code does not need social credentials to measure color, generate content, or publish the web archive.

---

## Phase 1 — Put the project on your Mac

### 1. Unzip the production package

Move the `pantone-challenger` folder into a permanent location, such as:

```text
Documents/GitHub/pantone-challenger
```

Do not work from the Downloads folder if you can avoid it.

### 2. Open Terminal

Press `Command + Space`, type `Terminal`, and press Return.

### 3. Enter the project folder

Adjust the path if you used a different location:

```bash
cd ~/Documents/GitHub/pantone-challenger
```

### 4. Run the setup script

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The script creates an isolated Python environment, installs the application, installs the Chromium browser used for capture, and runs the test suite.

### 5. Activate the environment

```bash
source .venv/bin/activate
```

### 6. Confirm the real panel

```bash
challenger doctor
challenger sources
```

The expected panel is:

```text
48 sources
12 sectors
4 sources per sector
```

Do not continue if `challenger doctor` reports missing configuration.

---

## Phase 2 — Create the GitHub repository

The easiest route is GitHub Desktop.

### GitHub Desktop route

1. Install and sign in to GitHub Desktop.
2. Choose **File → Add Local Repository**.
3. Select the `pantone-challenger` folder.
4. Choose **Publish repository**.
5. Repository name: `pantone-challenger`.
6. Keep it private during the first week if you prefer.
7. Publish the repository.

The command-line route is also available:

```bash
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

The production package already contains Git history, so do not run `git init` again.

---

## Phase 3 — Give GitHub Actions the permissions it needs

In the GitHub repository:

1. Open **Settings**.
2. Open **Actions → General**.
3. Under workflow permissions, choose **Read and write permissions**.
4. Enable the option allowing GitHub Actions to create pull requests.
5. Save.

Then:

1. Open **Settings → Pages**.
2. Set the deployment source to **GitHub Actions**.
3. Save if GitHub presents a save button.

No social credentials are needed yet.

---

## Phase 4 — Run the first real capture

Do this from GitHub rather than from your laptop. It tests the exact production environment.

1. Open the repository’s **Actions** tab.
2. Select **Daily Challenger**.
3. Choose **Run workflow**.
4. Use:
   - Date: `auto`
   - Maximum sources: `0`
   - Force rebuild: off
5. Run it.

`0` means the full 48-source panel. A smaller number is only a live engineering smoke test and cannot pass the production quality gate.

### What the workflow does

It will:

1. Install Chromium.
2. Visit all 48 official marketing pages.
3. Capture two fixed viewports from each usable page.
4. detect block/challenge pages;
5. remove exact and highly conservative near duplicates;
6. extract per-source color palettes;
7. apply source-level baseline suppression;
8. score cross-industry color clusters;
9. apply the data-quality gate;
10. generate the feed post, Story cards, caption, and evidence files;
11. upload raw screenshots as a private, temporary workflow artifact;
12. open a daily review pull request only if the gate passes.

A failed quality gate is a correct product outcome. It means “do not publish today,” not “invent a result.”

---

## Phase 5 — Review the first daily pull request

Open the pull request titled:

```text
Yesterday’s Challenger — YYYY-MM-DD
```

Review:

1. `feed-post.png`
2. all four Story cards;
3. `caption.txt`;
4. `result.json`;
5. the number of usable sources and sectors;
6. `capture-report.json` for failures;
7. the private raw-capture workflow artifact if the outcome looks suspicious.

Merge only when:

- the source count is credible;
- the result has cross-sector support;
- the post does not make a claim broader than the panel;
- the graphics rendered correctly;
- no obviously duplicated challenge page survived;
- the source panel itself did not change unexpectedly.

Do **not** reject or alter the winner because it is ugly. That is part of the project rule.

Merging the pull request is the formal publication approval.

---

## Phase 6 — Launch the public archive

After the pull request is merged, the **Deploy public archive** workflow runs.

Open:

```text
Settings → Pages
```

GitHub will show the public Pages address. It normally resembles:

```text
https://YOUR_USERNAME.github.io/pantone-challenger/
```

Verify:

1. the latest color appears;
2. the archive page opens;
3. source links work;
4. JSON evidence files are reachable;
5. social images load from `/assets/YYYY-MM-DD/`.

Store the exact Pages origin. It becomes the `PUBLIC_BASE_URL` repository variable.

---

## Phase 7 — Create the social identity

A clean launch identity could be:

```text
Display name: Pantone Challenger
Descriptor: The Commercial Color Index
Bio: One algorithm. One color. Every day. Watching what brands actually put into the world. Independent; not affiliated with Pantone.
```

Because “Pantone” is a protected brand, keep the independence statement visible and avoid Pantone logos, proprietary color numbers, branded swatch shapes, or language suggesting official affiliation. Consider using **Challenger Color Index** as the account handle even if the project title remains Pantone Challenger.

For Instagram automation, the account needs to be an eligible professional account and authorized through Meta’s current official content-publishing flow. Platform requirements and permission names can change; use Meta’s current official setup rather than copying credentials from an old tutorial.

---

## Phase 8 — Add repository variables

Open:

```text
Settings → Secrets and variables → Actions → Variables
```

Add:

```text
PUBLIC_BASE_URL
```

Value: the exact GitHub Pages origin without a trailing slash.

Add:

```text
META_GRAPH_VERSION
```

Value: the currently supported Graph API version shown in the Meta application.

For the initial period also add:

```text
AUTO_PUBLISH=false
PUBLISH_PLATFORM=instagram
INCLUDE_STORIES=false
```

Keep `AUTO_PUBLISH` false until manual publishing succeeds and the daily output is consistently trustworthy.

---

## Phase 9 — Add encrypted social secrets

Open:

```text
Settings → Secrets and variables → Actions → Secrets
```

For Instagram add:

```text
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
```

For Bluesky instead add:

```text
BLUESKY_HANDLE
BLUESKY_APP_PASSWORD
```

Never put these values in `.env`, source code, screenshots, issues, pull requests, or chat messages.

The Meta access token must remain valid. Token renewal and expiration monitoring are operational requirements for Instagram automation.

---

## Phase 10 — Publish the first social post manually

After the daily pull request has been merged and Pages has finished deploying:

1. Open **Actions**.
2. Select **Publish approved social package**.
3. Choose **Run workflow**.
4. Use:
   - Date: `latest`
   - Platform: `instagram` or `bluesky`
   - Include Stories: off for the first test
   - Force retry: off
5. Run it.
6. Confirm the post appears correctly on the account.
7. Confirm the workflow creates a completion tag and publication receipt.

The workflow creates a publish-lock tag before contacting the social API. If a request fails after the platform may have received it, the lock prevents a blind retry. Check the account before ever using **Force retry**.

For Instagram Stories, run a separate approved test with **Include Stories** on only after feed publishing works.

---

## Phase 11 — Begin the public run

For the first seven successful days:

- review every daily pull request;
- publish manually;
- record recurring source failures;
- do not change the scoring formula;
- do not replace the winner;
- allow the per-source baselines to calibrate.

After at least seven successful days, momentum becomes active. Thirty days produces a more meaningful baseline.

A sensible launch announcement happens after the first result is visible, not before:

```text
Pantone Challenger is live.

Every day it watches a fixed panel of commercial marketing pages and publishes the color that most unusually crossed brands and industries the day before.

The machine chooses the color. It is not allowed to reconsider because the answer is ugly.
```

---

## Phase 12 — Optional automatic publishing

Only after the manual period:

1. Confirm the latest scheduled daily pull requests are consistently healthy.
2. Decide how approval will happen:
   - Continue merging each pull request manually; or
   - configure a trusted auto-merge policy after checks pass.
3. Set the repository variable:

```text
AUTO_PUBLISH=true
```

The morning scheduled publisher then posts the latest approved result. “Approved” still means the daily result exists on `main`; an unmerged pull request cannot be published.

Keep `INCLUDE_STORIES=false` initially. Story automation can be enabled separately after several successful tests.

---

## Daily operating routine

The normal human workload should be approximately:

1. Open the daily pull request.
2. Inspect the card, caption, sample size, and failures.
3. Merge or close.
4. Confirm the site/publisher workflows finish.

When the quality gate blocks a day, do not force a post. Investigate whether several sources changed structure, blocked GitHub runners, or returned blank pages.

---

## When to replace a source

Replace a panel source only when it:

- fails consistently over multiple days;
- stops being an official marketing page;
- permanently redirects to a login or challenge;
- no longer contributes meaningful visual marketing;
- creates a structural sector imbalance.

Make replacements in a dedicated pull request, update the panel version, explain the reason, and do not backfill historical days under the new panel.

---

## Launch checklist

- [ ] Production package is in your GitHub repository.
- [ ] `challenger doctor` passes.
- [ ] Source panel shows 48 sources and 12 sectors.
- [ ] GitHub Actions has read/write and pull-request permission.
- [ ] GitHub Pages uses GitHub Actions.
- [ ] First full real capture completed.
- [ ] Daily result passed the quality gate.
- [ ] Raw capture evidence was reviewed.
- [ ] First daily pull request was merged.
- [ ] Public archive is live.
- [ ] Independence/trademark disclaimer is visible.
- [ ] First social publish was manually approved.
- [ ] Completion tag and receipt were created.
- [ ] Automatic publishing remains off during calibration.
