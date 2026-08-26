# Social Publishing Design

## Default state

Social publishing is disabled until account credentials are added.

The data product, daily images, caption, GitHub pull request, and public archive all operate without social credentials.

## Approval model

1. Nightly capture opens a pull request.
2. The pull request contains the complete daily publishing package.
3. Merging the pull request places the result on `main`.
4. The public archive deploys.
5. A manual or scheduled publisher can then use the public image URL.

An unmerged result cannot be selected by the publisher.

## Instagram

The publisher expects:

```text
PUBLIC_BASE_URL
META_GRAPH_VERSION
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
```

The feed image must be publicly reachable because Meta’s publishing flow retrieves it by URL.

Story publishing is optional and disabled by default. It is attempted only with the explicit `--include-stories` flag or repository variable.

Use a professional Instagram account and Meta’s currently supported official content-publishing authorization flow. Permission names, account linkage requirements, token lifetimes, and supported media behavior can change. Do not rely on an old third-party tutorial.

## Bluesky

The publisher expects:

```text
BLUESKY_HANDLE
BLUESKY_APP_PASSWORD
```

Use an app password rather than the primary account password.

## Duplicate prevention

Before automatic publishing, the workflow pushes:

```text
publish-lock-PLATFORM-YYYY-MM-DD
```

If that lock exists without a completion tag, automation stops. It does not assume the prior API call failed.

After confirmed success it adds:

```text
published-PLATFORM-YYYY-MM-DD
```

and writes `published.json`.

A force retry is intentionally difficult. Check the actual social account before clearing or bypassing a lock.

## Recommended rollout

Days 1–7:

- review pull requests;
- post manually through the workflow;
- keep Stories manual or disabled;
- verify token behavior;
- inspect source failure patterns.

Days 8–30:

- consider scheduled feed publishing;
- continue manual merge approval;
- keep a human eye on every result;
- activate Story automation only after separate testing.

After Day 30:

- evaluate the baseline;
- publish a monthly color strip;
- audit whether any sector or brand is systematically overrepresented;
- decide whether the panel should remain fixed for the rest of the year.
