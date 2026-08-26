# Security

## Secrets

Never commit social tokens or passwords. Use encrypted GitHub Actions secrets.

The `.env.example` file contains names only. A real `.env` file is ignored.

## Reporting

For a security issue, open a private GitHub security advisory rather than a public issue.

## Publisher safeguards

The social publisher:

- requires an explicit approval flag;
- refuses quality-gate failures;
- refuses dates already carrying a local publication receipt;
- verifies that Instagram assets are publicly reachable;
- uses a Git tag reservation lock in scheduled automation;
- stops on ambiguous partial failure rather than blindly retrying.

A stale publish lock must be investigated against the actual social account before retry.
