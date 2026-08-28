# Release procedure

A release is evidence-driven and local-only.

1. choose the exact candidate commit and require a clean worktree;
2. run database migrations against the local release PostgreSQL instance;
3. run `./scripts/test release`;
4. run `./scripts/benchmark` and retain the performance artifact;
5. run backup/restore and migration/replay scenarios;
6. verify `.github/workflows/` is absent/empty;
7. inspect the exact-commit `TestEvidenceBundle` for failures, blocked required suites, unexplained skips, dirty worktree, and environment fingerprints;
8. build the container from the same commit and perform health/readiness plus a Testing Grounds smoke journey;
9. only then tag/publish the release manually through the approved local process.

No GitHub Actions release, test, build, or deployment workflow may be introduced.
