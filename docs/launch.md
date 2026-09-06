# V1.5 launch sequence

1. Install V1.5 on a repair branch and wait for CI.
2. Merge the repair only after CI passes.
3. Keep `ENABLE_DAILY_SCHEDULE` unset or false.
4. Run seven manual calibration days.
5. Merge valid review-only and baseline-only days so the source baselines warm up.
6. Inspect private contact sheets and collection reports.
7. Replace or retarget persistently blocked sources.
8. Confirm no logo, overlay, favicon, site background, or syndicated campaign is acting as trend evidence.
9. After at least seven valid days, review whether New/Rising/Spreading/Surging labels are plausible.
10. Enable GitHub Pages and use the site as the link-in-bio history layer.
11. Post manually for at least seven approved ready days.
12. Test the social workflow in dry-run mode before providing any publishing credential.
13. Set `ENABLE_DAILY_SCHEDULE=true` only after manual review has been consistently clean.
