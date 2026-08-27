# Claude / Claude Code Instructions

Before making changes, read and follow:

1. [`AGENTS.md`](AGENTS.md) — repository-wide agent execution policy and current v0.1 implementation contract.
2. [`PLAN.md`](PLAN.md) — the single authoritative architecture, roadmap, milestone exit criteria, and definition of done.

Do not create a separate Claude-specific architecture or roadmap. If this file and the canonical documents appear to conflict, `PLAN.md` controls architecture and `AGENTS.md` controls agent workflow.

Work from the earliest incomplete relevant milestone unless the user explicitly directs otherwise. Preserve deterministic command/event architecture, server authority, replay/versioning, licensing boundaries, and non-blocking async behavior.