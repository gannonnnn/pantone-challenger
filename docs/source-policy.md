# Source and Rights Policy — Version 1.3

## Inclusion criteria

A panel source must be:

- publicly reachable without authentication;
- owned or officially operated by the represented company or organization;
- substantially commercial or promotional;
- visually meaningful at the configured desktop viewport;
- assigned to exactly one declared sector in the registry;
- appropriate for limited automated observation.

## Exclusions

The project excludes login-only pages, paywalls, private accounts, CAPTCHA circumvention, anti-bot evasion, personal data, user-generated feeds, and unofficial logo repositories.

## Access behavior

Pantone Challenger limits concurrency and request rate, uses fixed viewports, does not log in, and records blocked pages as unavailable. It does not repeatedly retry a challenged source in a way intended to bypass restrictions.

## Evidence regions

Full-page screenshots are private diagnostics. Public color support must come from an eligible marketing-creative region that passes the configured size and confidence checks.

Headers, navigation, footers, cookie interfaces, modal overlays, chat widgets, logos, favicons, and small icons are not public color evidence.

## Raw captures

Raw page frames, region screenshots, and evidence contact sheets are used for extraction, audit, and debugging. They are excluded from Git and from the public archive. GitHub Actions retains them only for the configured limited period.

## Public evidence

Public packages may include:

- company name;
- authoritative sector;
- official source URL;
- capture status and counts;
- local derived color swatch and HEX;
- perceptual distance and normalized share;
- scoring and methodology metadata;
- original Pantone Challenger graphics;
- an optional manually approved company mark.

V1.3 does not automatically republish campaign photography.

## Brand marks

Runtime favicon and header-logo scraping is not permitted in public assets. Every source defaults to text-only attribution.

A mark may be used only when:

1. it has been manually obtained from an appropriate first-party source;
2. it has been reviewed for legibility and presentation;
3. its repository path is declared in `config/sources.yml`;
4. `brand_mark_status` is set to `approved`;
5. its use remains modest and identification-only.

If any condition fails, the renderer uses the company name without a logo.

## Attribution and endorsement

A company’s inclusion documents an observation source. It does not imply sponsorship, endorsement, affiliation, partnership, or coordination. The project must not present monitored companies as clients or sponsors.

## Panel changes

A source should be replaced only when it is persistently unusable, ceases to be official or promotional, or creates a structural panel problem. A replacement must be documented with its reason, effective date, sector, and panel-version change. Sources must never be swapped merely to produce a preferred color.
