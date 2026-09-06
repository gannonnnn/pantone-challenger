# Approved brand marks

This directory is intentionally empty in a fresh installation.

Pantone Challenger never scrapes a favicon and presents it as a polished logo. A public mark may be used only when:

1. it came from a first-party or otherwise authorized source;
2. it is manually reviewed;
3. it is a transparent PNG with adequate source resolution;
4. the corresponding source registry entry sets `brand_mark_status: approved`;
5. the registry points to the normalized output path.

Use `python scripts/normalize_brand_mark.py INPUT.png OUTPUT.png` to create a contained, padded presentation asset. When no approved mark exists, the renderer uses the company or source name as text. This is the expected default, not an error.
