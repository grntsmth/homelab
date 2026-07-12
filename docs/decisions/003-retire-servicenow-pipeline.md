# ADR-003: Retire the ServiceNow incident pipeline

**Date:** 2026-07-12
**Status:** accepted

## Context

sn-translator (FastAPI, `apps/sn-translator/` until this commit) bridged
Alertmanager webhooks into ServiceNow incidents on a free Personal
Developer Instance: fingerprint-deduplicated create-on-firing /
resolve-on-clear, SQLite state, tested batch semantics. The pipeline was
verified end-to-end on 2026-07-12 — rule → Alertmanager →
`team=infrastructure` route → translator → PDI.

The PDI has since **expired** (ServiceNow reclaims idle developer
instances), and standing up another one buys nothing: the learning goals
— webhook receiver design, incident lifecycle, dedup across restarts,
enterprise ITSM field-mapping quirks — are met and documented, and
day-to-day operations only need Discord.

## Decision

- Undeploy sn-translator (Deployment, Service, PVC, SealedSecret,
  private env ConfigMap) and remove `apps/sn-translator/` from the tree —
  per this repo's rule that the tree shows what runs. The code, its
  test suite, and the pipeline architecture live in git history and the
  chaos README's history section.
- Remove the `servicenow` receiver and route from Alertmanager. Alert
  routing is Discord-only.
- **Keep the `team: infrastructure` labels** on the alert rules — they
  are the routing taxonomy a future ticketing receiver (PagerDuty,
  ntfy, a revived SN instance) would key on, and they cost nothing.

## Consequences

- The chaos pipeline's "closed loop" artifact is now: experiment →
  alert → Discord notification → auto-resolve, which is fully
  self-hosted and cannot expire out from under the lab.
- If ticket-lifecycle work becomes relevant again, the translator
  pattern is one `git checkout` away; a revival should reuse the
  fingerprint-dedup design and the batch-isolation semantics its tests
  encode.
