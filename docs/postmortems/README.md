# Postmortems

Blameless writeups of incidents that affected the homelab. The bar for writing one is *user-visible disruption* or *near-miss with lessons worth saving*, not every transient blip.

## Why blameless

Single-operator infra makes "blame" a meaningless concept — there's only one operator. But the discipline still applies: focus on the *system* that allowed the incident, not the *decision* that triggered it. The point is to fix the next class of failure, not to litigate this one.

## Template

Each postmortem is a single Markdown file named `YYYY-MM-DD-<short-slug>.md`. Suggested structure:

```markdown
# <Incident title>

**Date:** YYYY-MM-DD
**Duration:** <e.g., 14:32 → 15:11 ET (39 min)>
**Severity:** {SEV-1 | SEV-2 | SEV-3}
**Author:** <name>
**Status:** {draft | review | final}

## Summary

Two or three sentences. What broke, who was affected, how it was resolved.
A reader who reads only this section should know whether to keep reading.

## Impact

- **User-visible:** what was unavailable, degraded, or wrong (e.g., Grafana
  unreachable for 39 min, alerts silently dropped, dashboard data missing
  for the window).
- **Internal:** what the operator had to do to recover (manual steps,
  on-call time, data loss).
- **Scope:** which nodes, namespaces, services were affected.

## Timeline (UTC or ET — pick one)

Bullet points, oldest first. Include the moment the system first
misbehaved, not just when the alert fired.

- `14:32` — `DiskSpaceLow` alert fires for star-garden.
- `14:34` — Operator acks in Discord; opens dashboard.
- `14:41` — Identified Prometheus TSDB growth; PVC at 97%.
- `15:11` — Retention reduced to 15d, compaction triggered, disk recovered.

## Root cause

The actual underlying cause, in technical detail. If you find yourself
writing "human error," keep asking why — the human error is almost always
downstream of a missing guardrail.

## Contributing factors

Things that made the incident worse or harder to detect/resolve.
Examples: stale alerts, missing runbook, dashboards not loaded,
ambiguous metric names, single-point-of-failure.

## What went well

Equally important. Recovery paths that worked, alerts that fired
correctly, automation that held up. Worth identifying so we keep them.

## What went poorly

The honest list. Detection delay, mitigation overhead, missing tooling.

## Action items

Concrete, owner-assigned, tracked. Each item should be small enough to
land in one PR.

| # | Action | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Add a Prometheus TSDB size alert at 80% PVC | me | 2026-MM-DD | open |
| 2 | Document retention-tuning procedure in `runbooks/` | me | 2026-MM-DD | open |

## Lessons learned

The generalizable takeaway. Often: "we monitored X, but the leading
indicator was Y." Write the thing future-me needs to know, not the
thing present-me already knows.
```

## Index

| Date | Incident | Severity |
|---|---|---|
| [2026-05-30](2026-05-30-kube-prom-stack-cutover-rollback.md) | kube-prometheus-stack cutover rolled back — pod-network scraping infeasible | SEV-3 |
