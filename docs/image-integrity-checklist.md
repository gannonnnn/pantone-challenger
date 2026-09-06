# Image integrity checklist

This checklist exists because earlier prototypes produced misleading neutrals, enlarged favicons, cropped marks, invisible runner-up swatches, and evidence cards whose logos did not prove the selected color.

## Before analysis

- Hide structural header, navigation, footer, logo, icon, modal, cookie, chat, and account elements.
- Reject verification, challenge, consent, subscription, regional-selection, and offer overlays.
- Reject regions smaller than 280 × 180 pixels.
- Reject blank frames, loading strips, flat placeholders, and extremely low-information regions.
- Deduplicate overlapping nested regions and visually identical regions.
- Reject redirects outside the source's approved host list.
- Use fallback pages only on approved first-party hosts.

## During color extraction

- Composite transparency consistently.
- Trim transparent outer padding.
- Downsample deterministically.
- Use a perceptual color space for clustering.
- Keep neutrals in diagnostics, but apply the exceptional-neutral publication gate.
- Give each independent source one equal cross-source vote.
- Compare persistent colors with the same source's history.
- Reduce exact and near-duplicate campaigns across sources.

## Public rendering

- Render swatches directly from stored HEX values.
- Test the center pixel of winner and runner-up fields.
- Add visible boundaries to light swatches.
- Calculate readable text color from contrast.
- Never use `cover` for logos.
- Never crop a logo.
- Never enlarge a raster logo more than 2×.
- Reject favicon-size marks.
- Prefer a clean text label when a manually approved logo is unavailable.
- Place the local matched swatch before the attribution mark.
- Never publish full analyze-only source images.

## Human review

- Does every displayed source have a plausible local matched swatch?
- Are company/source names and sectors correct according to the registry?
- Is one platform, domain, campaign, or creator manufacturing the result?
- Is the Challenger actually emerging, or merely common?
- Do ties and palette pairs represent different statistical cases?
- Is the result labeled calibration, baseline-only, blocked, or ready correctly?
