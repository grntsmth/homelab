# ADR-001: Design around the broken pod network (for now)

**Date:** 2026-07-12
**Status:** accepted
**Context links:** [2026-05-30 cutover postmortem](../postmortems/2026-05-30-kube-prom-stack-cutover-rollback.md), [connectivity check runbook](../runbooks/pod-to-pod-connectivity-check.md)

## Context

Direct pod-to-pod TCP does not work on this cluster — at any distance,
including same-node. k3s ships kube-router as its NetworkPolicy enforcer;
its `KUBE-ROUTER-FORWARD` chain sits first in `FORWARD` (default DROP) and
pod-network packets never reach flannel's ACCEPT rules. The flannel
`ACCEPT all to 10.42.0.0/16` rule has matched **0 packets** over the
cluster's lifetime. Two paths do work, which is why production never
noticed:

- **hostNetwork pods** — host routing applies, pod IPs never involved.
- **ClusterIP services from pod-network pods** — kube-proxy DNAT +
  MASQUERADE makes the packet look `src-type=LOCAL`, which kube-router
  explicitly accepts.

This stayed hidden for 63 days until the kube-prometheus-stack migration
tried ServiceMonitor-based scraping (pod-IP endpoints) and 12 of 13
targets were unreachable. The migration was rolled back cleanly.

## Decision

**Accept the constraint and design for it** rather than fixing the CNI
now (postmortem action item 3, option c). Concretely:

1. Monitoring components run `hostNetwork: true` pinned to the watchtower
   node; Prometheus reaches Alertmanager at `localhost:9093`.
2. Cross-component calls target **NodePorts on the node that hosts the
   pod** (e.g. Alertmanager → sn-translator at `<control-plane>:30891`).
   Cross-node NodePort DNAT rides the broken pod network and must not be
   used — this exact mistake kept kube-state-metrics unscraped for weeks.
3. Pod-network pods may talk to ClusterIP services, never to pod IPs.
4. Any tooling that assumes pod-network health (ServiceMonitors,
   PodMonitors, operator-style service discovery) is out of scope until
   this ADR is superseded.
5. The [connectivity runbook](../runbooks/pod-to-pod-connectivity-check.md)
   is the canary: run it before adopting anything that touches pod
   networking, and after any k3s upgrade.

## Alternatives considered

- **`--disable-network-policy` on k3s** — one flag, removes kube-router,
  and flannel forwarding likely starts working. Rejected for now: every
  NetworkPolicy in the cluster silently stops being enforced, including
  genuinely load-bearing same-node isolation around private workloads on
  the control-plane node (RCON port isolation, egress allowlists on pods
  running third-party plugin jars). Losing enforcement invisibly is worse
  than the constraint.
- **Replace the CNI (Cilium/Calico)** — the honest long-term fix, and the
  natural moment to re-attempt the kube-prometheus-stack migration.
  Deferred: it is a multi-day change with real blast radius on a cluster
  where the 1-CPU worker is already memory-tight, and the hand-rolled
  stack meets current needs.

## Consequences

- The hand-rolled monitoring stack in `monitoring/monitoring.yml` is the
  deliberate present, not a stopgap embarrassment. It gets first-class
  care: overlays, provisioned dashboards, tested alert routing.
- The dormant kube-prometheus-stack/Flux-sync trees were removed from the
  repo (see git history at tag-time 2026-07-12); re-attempting that
  migration starts from this ADR, the postmortem, and a green
  connectivity check — not from stale manifests.
- Revisit trigger: when a CNI replacement is scheduled, or when a
  workload genuinely needs pod-to-pod (not before).
