Pantone Challenger v1.0.1 hotfix
================================

This hotfix corrects two launch issues in v1.0.0:

1. CI test failure
   The baseline-suppression test accidentally reused an unchanged screenshot hash,
   which activated a separate unchanged-page penalty. The test now isolates the
   intended behavior and adds explicit coverage for unchanged-page suppression.

2. GitHub Pages failure in a private repository
   The Pages workflow now exits successfully with an explanatory notice while the
   repository is private. Daily Challenger can still run. When the repository is
   made public, the normal Pages build and deploy jobs run.

Files to copy into the local cloned repository, preserving paths:

  .github/workflows/pages.yml
  tests/test_scoring.py

Then commit and push with this message:

  fix: correct CI test and skip Pages for private repo

Expected result after push:

  CI / test                         passes
  Deploy public archive / notice   passes
  Deploy public archive / build    skipped while private
  Deploy public archive / deploy   skipped while private
