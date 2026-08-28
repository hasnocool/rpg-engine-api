# Local release benchmarks

Benchmarks are executed only on the designated local test environment. They never run in GitHub Actions.

Run:

```bash
./scripts/benchmark
./scripts/test performance
```

The initial budgets are intentionally conservative regression floors, not marketing claims. Tighten them only after collecting repeatable local evidence from representative hardware.

Workloads cover in-memory event append, public command processing, deterministic scheduler throughput, event fanout, deterministic controller decisions, and full runtime reconstruction. PostgreSQL-specific throughput should be recorded separately by the local agent when the integration environment is active.
