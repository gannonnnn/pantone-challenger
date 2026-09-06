# Image, Scraping, and Rendering Safety

This checklist is part of the product contract. A run that cannot satisfy it is review-only or blocked.

## Capture

- Use a real browser for webpage sources and wait for a stable visual state.
- Restrict redirects to declared first-party hosts.
- Hide or reject headers, navigation, footers, logos, wordmarks, cookie/privacy layers, account prompts, chat widgets, verification gates, and modal overlays.
- Prefer identifiable creative regions (`main`, `section`, `article`, large images, video posters, and background-image sections) over full-page screenshots.
- Reject blank regions, loading strips, tiny slivers, low-information placeholders, and overlapping duplicates.
- Store source URL, frame, bounding box, region confidence, and rejection reason.

## Downloaded images

- Require an image content type and successful decode.
- Apply EXIF orientation before analysis.
- Reject implausible dimensions and decompression-bomb-sized files.
- Normalize alpha safely for analysis; never turn transparency into black evidence.
- Hash exact and perceptual duplicates.
- Respect `rights_mode`: public-domain and licensed images may be handled according to their terms; `analyze_only` images stay in private evidence artifacts.

## Logos

- Logos are attribution only and never color evidence.
- Public assets may use only manually approved marks from `assets/brands/`.
- Never use a runtime favicon as a public logo.
- Fit with `contain`, preserve aspect ratio, trim transparent padding, retain internal breathing room, and never enlarge a raster mark more than 2x.
- Use a clean text fallback when a mark fails validation.

## Social rendering

- Feed: 1080 x 1350. Stories: 1080 x 1920.
- Render swatches directly from the stored HEX; verify center pixels in tests.
- Add a visible boundary around very light swatches.
- Choose text color by contrast rather than by hue label.
- Wrap and auto-fit long names; fail validation on overflow.
- Do not stretch, cover-crop, or distort evidence art.
- Public evidence cards show local matched swatches and attribution, not full copyrighted creative by default.
- Add alt text files for every social image.
- Verify every extracted swatch and candidate HEX against decoded source pixels before rendering.
- Include a private proof sheet that isolates the pixels matching each candidate.

## Quality behavior

A technically successful scrape is not automatically publishable. The workflow may produce:

- `ready`
- `review_only`
- `baseline_only`
- `blocked`

No forced daily winner is allowed.
