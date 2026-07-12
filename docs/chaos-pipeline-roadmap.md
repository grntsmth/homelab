# Chaos Pipeline Roadmap

Status of the chaos engineering pipeline (`chaos/`, `apps/sn-translator/`)
— revised 2026-07-12 after the repo restructure. The original phased plan
from May assumed the kube-prometheus-stack migration would land; it
didn't ([postmortem](postmortems/2026-05-30-kube-prom-stack-cutover-rollback.md),
[ADR-001](decisions/001-design-around-broken-pod-network.md)), so this
roadmap was rebased onto the hand-rolled stack.

## Done

- ServiceNow credentials sealed and committed (`apps/sn-translator/manifests/sealed-secret.yml`).
- sn-translator built, deployed, hardened (batch isolation, hibernation
  detection, tests), wired into the **live** Alertmanager via the
  `team = infrastructure` route.
- Chaos Mesh installed via Flux HelmRelease, healthy since 2026-05-31.
- Alert delivery verified end-to-end 2026-07-12: rule → Alertmanager →
  sn-translator → PDI answered (hibernating; wake pending). The
  alerting-path itself is now monitored (`NotificationDeliveryBroken`,
  platform-health dashboard).
- CI covers `chaos/` (CRD-aware kubeconform) and sn-translator
  (ruff + pytest).
- SLO groundwork the old Phase 3 wanted: blackbox probes, availability
  recording rules, multi-window burn-rate alerts, `ecosystem-slo`
  dashboard.

## Revised (2026-07-12, later): ServiceNow retired

The PDI expired before it could be woken; the pipeline's ServiceNow leg
was retired the same day it was verified — see
[ADR-003](decisions/003-retire-servicenow-pipeline.md). The closed loop
is now experiment → alert → **Discord** → auto-resolve, fully
self-hosted.

## Next

1. **First real chaos session** — apply `chaos/experiments/pod-kill.yml`
   against `ecosystem`, watch detection → incident → auto-resolve, and
   write the timeline up as the second postmortem-grade artifact. Pair
   each experiment with a detection rule that provably fires (the
   committed host-health rules aren't tuned for 90-second faults).
2. **Chaos timeline dashboard** — chaos events + `ALERTS` + incident
   table on one screen; belongs in `monitoring/dashboards/` once there
   are real events to show.
3. **Runbook per chaos type** — written from the sessions, not ahead of
   them.

## Out of scope (unchanged)

Multi-cluster, self-service chaos workflows, change-management
integration — at single-operator scale the marginal value is in **running
the loop on real failures and writing it up**, not in more machinery.
Same for replacing the SQLite fingerprint store: fine at this scale.
