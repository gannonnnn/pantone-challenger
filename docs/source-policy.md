# Source and Rights Policy

## Inclusion criteria

A Version 1.1 source must be:

- publicly reachable without authentication;
- owned or officially operated by the represented brand or organization;
- substantially commercial or promotional;
- visually meaningful at a consistent desktop viewport;
- assignable to one declared sector;
- appropriate for limited automated observation.

## Exclusions

The production panel excludes:

- private accounts;
- login-only pages;
- paywalled pages;
- user-generated social feeds;
- scraped ad repositories without a clear permitted access method;
- pages requiring CAPTCHA circumvention;
- pages requiring anti-bot evasion;
- personal data;
- pages primarily containing news reporting rather than brand marketing;
- individual creators unless added under a separately declared panel.

## Access behavior

Pantone Challenger:

- identifies itself in its user agent;
- limits concurrency and adds request delay;
- captures only two fixed viewports per source;
- does not log in;
- does not bypass access controls;
- does not solve or outsource CAPTCHAs;
- records blocked pages as failures;
- does not repeatedly hammer a failing source.

Source operators may request removal. A removal should be documented as a panel change rather than hidden.

## Raw screenshots

Raw browser screenshots are used for:

- extraction;
- duplicate checks;
- private analyst review;
- debugging failed or surprising results.

They are excluded from Git, excluded from the public site, and retained only temporarily as private GitHub Actions artifacts.

## Public evidence

The public archive may include:

- source name;
- a first-party company mark captured from the official page header or official site icon;
- source URL;
- capture timestamp;
- screenshot hash;
- extracted color values;
- normalized shares;
- scoring components;
- capture status and error category;
- original Pantone Challenger graphics.

It does not republish the captured campaign photography in Version 1.1. When a company mark is unavailable or unusable, the project uses a typographic fallback rather than fetching an unofficial logo.

## Attribution

The source panel links to official pages. A source link or company mark documents where observation occurred; it does not imply endorsement, sponsorship, affiliation, or partnership. Company marks should be shown only alongside the evidence they identify, at a modest size, without alteration beyond normalization needed for legibility.

## Trademark and brand presentation

The project must not:

- use Pantone logos;
- use proprietary Pantone color codes;
- copy Pantone swatch layouts in a way that suggests affiliation;
- describe itself as an official Pantone product;
- alter monitored company marks to imply a partnership;
- use company marks as decorative sponsorship badges;
- suggest that monitored brands endorse the index.

The independence disclaimer appears in the public site and caption.

## Source replacement process

A source should be replaced only after documented evidence that it is persistently unusable or no longer fits the panel.

A replacement pull request must state:

- old source;
- new source;
- sector;
- reason;
- effective date;
- panel version change;
- expected impact on comparability.

No replacement should be made merely because a brand’s colors are producing inconvenient results.
