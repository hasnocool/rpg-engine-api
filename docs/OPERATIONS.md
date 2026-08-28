# Operations runbook

## Backup

Use the campaign export/backup APIs to generate integrity-hashed event-history packages. Store backups outside the database and verify the package digest before considering a backup usable.

A backup is not proven until the local recovery suite restores it into an empty target and verifies replay/canonical hashes.

## Restore

1. stop writes to the target;
2. provision an empty compatible database;
3. run Alembic to the expected schema;
4. validate the package through `/api/v1/imports/campaign/validate`;
5. restore using the admin restore endpoint;
6. rebuild runtime projections;
7. compare replay/live canonical hashes;
8. run the local recovery/playtest profile before reopening traffic.

## Content migration

1. publish the candidate immutable content version;
2. propose the revision;
3. review semantic diff and campaign impact;
4. run the isolated migration sandbox dry-run;
5. inspect reachability/content-quality results;
6. create/verify the automatic pre-activation checkpoint;
7. activate only compatible revisions;
8. continue play and verify replay;
9. rollback only when reverse migration is declared valid; otherwise branch from the checkpoint.

## Incident recovery

For database disconnects or process crashes, do not manually edit event history. Restore service/database availability, restart the service, allow deterministic reconstruction, check readiness and outbox/projection health, then run targeted local recovery tests if state integrity is uncertain.
