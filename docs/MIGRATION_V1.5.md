# V1.5 migration notes

V1.5 is cumulative. It preserves the evidence-integrity, equal-vote, overlay rejection, neutral handling, recurrence, annual summary, and calibration protections from the V1.3/V1.4 line.

The new source matrix does not make every source equally meaningful. Each record declares a domain, signal stage, scale class, and panel. Scoring applies platform and domain caps before ranking.

API sources requiring credentials remain disabled until their secrets are added. Browser and open-access sources must pass the same image and provenance quality gates as every other source.

Existing approved daily archives are preserved by the installer. Local `.env` files and manually curated `assets/brands` files are not overwritten.
