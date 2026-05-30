# kube-prometheus-stack cutover rolled back — pod-network scraping infeasible

**Date:** 2026-05-30
**Duration:** ~21:30 → 22:30 ET (60 min, planned migration window)
**Severity:** SEV-3 — planned change, rolled back cleanly, no user-visible outage outside the migration window itself
**Author:** Grant (with Claude as driver)
**Status:** final

## Summary

Attempted to migrate the homelab's handwritten Prometheus + Alertmanager +
Grafana stack to the `kube-prometheus-stack` Helm chart (Phase 1.3 of the
chaos pipeline roadmap). The chart installed cleanly but its
ServiceMonitor-based scraping required pod-to-pod connectivity over the
pod network, which **doesn't actually work on this cluster**. The chart's
new Prometheus could scrape only itself. Rolled back to the
hostNetwork-based handwritten stack; data preserved, all alerts restored.

The migration failure surfaced a much older, dormant problem: the cluster's
pod network has been broken since installation, hidden by the fact that
every production workload either runs `hostNetwork: true` or is reached via
ClusterIP only.

## Impact

- **User-visible:** ~5 min metrics/alerting outage during the planned
  teardown/install window; another ~5 min during rollback. Discord
  notifications gap during both windows (and were already silently broken
  pre-cutover — see "Drift surfaced" below).
- **Internal:** 60 min of operator time. No data loss — Prometheus TSDB
  PVC (30d history) and Grafana PVC preserved through both transitions.
- **Scope:** `monitoring` namespace, both nodes. Workload namespaces
  (`ecosystem`, `minecraft`, `postgres`) untouched.

## Timeline (ET)

- `21:30` — Pre-flight: chart version stale (78.x pinned, 86.1.0 latest)
  and `alertmanager-discord` Secret referenced by `discord-relay.yml`
  doesn't exist in cluster (pre-existing drift, surfaced by inspection).
- `21:35` — Two fixes committed: bump chart pin to `86.x`, mark
  Discord webhook secretRef `optional: true`.
- `21:40` — Phase 1 (additive prep): `admin-user` key patched into
  `grafana-admin` Secret; `k8s/alertmanager/` applied; new Discord relay
  Deployment Ready.
- `21:45` — Phase 2 (teardown): handwritten `prometheus`, `alertmanager`,
  `grafana` Deployments + `node-exporter` DaemonSet + ConfigMaps + Services
  deleted. PVCs preserved (verified).
- `21:48` — Phase 3 (apply chart): `kubectl apply -k k8s/kube-prometheus-stack/`.
- `22:00` — HelmRelease stuck "not reconciled" for 12 min.
  Diagnosis: `helm-controller` (star-garden) couldn't reach
  `source-controller` (high-palace) — cross-node DNS+TCP failure, same
  flannel issue called out in CLAUDE.md.
- `22:05` — `helm-controller` and `notification-controller` patched with
  `nodeSelector: kubernetes.io/hostname=high-palace`. Both rescheduled
  alongside `source-controller`. Reconcile resumed.
- `22:10` — HelmRelease `Ready=True`. All chart pods Running. Phase 4 begun.
- `22:12` — `k8s/prometheus-rules/` applied; PrometheusRules picked up by
  the chart's Prometheus.
- `22:15` — Smoke test: `/prometheus/targets` shows **1 of 13 targets up**
  — only `prometheus self-scrape`. All ServiceMonitor and external targets
  fail with "no route to host". This is the moment we knew rollback was
  needed.
- `22:18` — Diagnostic confirmed: pod-to-pod TCP via pod IPs fails
  cluster-wide, even same-node. `KUBE-ROUTER-FORWARD` is the first FORWARD
  chain rule; pod-network packets never reach the flannel `ACCEPT` rule.
- `22:20` — Rollback decision. Phase A: chart torn down, orphan PVCs removed.
- `22:25` — Phase B: `alertmanager-discord` placeholder Secret created,
  `kubectl apply -f monitoring/monitoring.yml` restored handwritten stack.
  Old Deployments rebound to preserved PVCs.
- `22:30` — Verification: 6 of 8 targets up (= pre-cutover baseline);
  30-day-old `up{job="node-high-palace"}` query returns `1` from
  2026-04-30T22:25:33; chaos pipeline pieces (sn-translator,
  alertmanager-chaos-config, Discord relay, PrometheusRules) all intact.
  Resolved.

## Root cause

The cluster's pod network does not actually carry pod-to-pod TCP traffic.
Diagnostics from `sn-translator` (pod IP `10.42.0.75`, on `high-palace`)
probing other pod IPs:

| Target | Same node? | Result |
|---|---|---|
| `10.42.0.75:8091` (self) | yes | OK |
| `10.42.0.130:53` (coredns) | yes | `No route to host` |
| `10.42.0.130:8181` (coredns ready) | yes | `No route to host` |
| `10.42.0.124:3101` (promtail) | yes | `No route to host` |
| `10.42.1.30:3101` (promtail star-garden) | no | `No route to host` |
| `10.43.0.10:53` (kube-dns Service) | n/a | OK |
| `10.43.0.1:443` (kubernetes Service) | n/a | OK |
| `10.43.56.123:3100` (loki Service) | n/a | OK |
| `169.254.169.254:80` (OCI metadata) | n/a | OK |

Inspection of iptables on `high-palace`:

- `FORWARD` chain default policy is `DROP`
- `KUBE-ROUTER-FORWARD` is the first rule (k3s ships kube-router as its
  NetworkPolicy enforcer)
- The flannel `ACCEPT all to 10.42.0.0/16` rule (FORWARD rule 5) shows
  **0 packets matched** across the cluster's 63-day uptime
- The flannel `ACCEPT all from 10.42.0.0/16` rule (rule 4) shows 164
  packets — these are pod → external paths that pick up MASQUERADE in
  POSTROUTING

What's actually working in production hides the problem:

- Every workload pod uses `hostNetwork: true` (monitoring, Loki, Grafana,
  Alertmanager, Prometheus, uptime-kuma) → pod IPs irrelevant, host
  routing applies
- Pod-network workloads (chronicle, sn-translator, Minecraft) reach
  collaborators only via **ClusterIP Service** → kube-proxy DNAT happens
  in `OUTPUT`/`PREROUTING`, then `MASQUERADE` rewrites source to the
  node IP, making the packet appear `src-type=LOCAL` to the destination
  pod's `KUBE-POD-FW-*` chain. kube-router has an explicit `ACCEPT for
  src-type LOCAL` rule that lets this path through.
- Direct pod-to-pod via pod IPs has the source intact (no MASQUERADE),
  no ClusterIP/DNAT in path, and never matches the LOCAL ACCEPT shortcut.

The kube-prometheus-stack chart's ServiceMonitors and PodMonitors
discover endpoints as **pod IPs**. Every chart-style scrape target was
therefore unreachable from the chart's Prometheus.

## Contributing factors

- **Hidden for 63 days.** No production workload ever needed direct
  pod-to-pod, so the broken state stayed dormant. The migration was the
  first time anything tried to exercise it.
- **CLAUDE.md only documented cross-node breakage**, not same-node. The
  diagnostic data shows same-node is broken too — broader than expected.
- **No connectivity smoke test in the homelab's runbook library.** A
  one-shot "two test pods, ping each other" check would have caught
  this years ago.
- **Helm-controller scheduled on star-garden by default.** It needed
  to reach source-controller (high-palace) and CoreDNS (high-palace) —
  both cross-node, both broken. This caused the initial chart-install
  stall (12 min) before the real problem (scrape failure) was visible.

## What went well

- **Rollback worked exactly as planned.** All four PVCs preserved,
  `kubectl apply -f monitoring/monitoring.yml` rebound to existing
  data, 30-day query confirmed history intact after rollback.
- **Pre-flight caught two issues before they bit during cutover** —
  chart-version staleness and the broken Discord secretRef. Both
  were addressed with small focused commits before any destructive step.
- **Sequenced phasing kept the destructive window narrow.** Additive
  prep (Phase 1) was reversible until the moment teardown started.
- **sn-translator stayed healthy throughout.** ServiceNow incidents
  could still be created/resolved via direct webhook POST during the
  full migration window. The translator's design (no dependency on
  Prometheus / Alertmanager / Grafana) paid off here.
- **The flux-controller nodeSelector patch is genuinely useful** even
  after rollback. Will keep it.

## What went poorly

- **No pre-flight connectivity test.** A 2-minute "can two pods talk to
  each other via pod IP" check would have aborted the migration before
  any teardown. Going forward this is a runbook prerequisite for any
  chart migration that uses ServiceMonitors.
- **`kube-state-metrics: enabled: false` was the wrong key** in the
  chart values — chart expects `kubeStateMetrics: enabled: false`
  (camelCase, top level). Silently ignored, resulting in a duplicate
  ksm pod being created during the brief chart uptime.
- **CLAUDE.md was misleading.** "Cross-node pod networking is unreliable"
  understates it — pod-to-pod is broken at all distances.

## Action items

| # | Action | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Update CLAUDE.md to reflect that pod-to-pod is broken cluster-wide, not just cross-node | me | 2026-06-06 | open |
| 2 | Add a `docs/runbooks/pod-to-pod-connectivity-check.md` runbook — two test pods, ping each other, document the working/expected output | me | 2026-06-06 | open |
| 3 | Decide on a CNI remediation path: (a) `--disable-network-policy` on k3s server, (b) replace kube-router with explicit Cilium/Calico install, or (c) accept the constraint and design around hostNetwork+ClusterIP forever | me | 2026-06-13 | open |
| 4 | Fix `kubeStateMetrics: enabled: false` in `k8s/kube-prometheus-stack/helmrelease.yml` so the next attempt doesn't duplicate ksm | me | next attempt | open |
| 5 | Keep the `helm-controller` + `notification-controller` nodeSelector pin to high-palace (whether persisted via patch manifest in `clusters/homelab/` or in the controllers' Deployments directly) | me | 2026-06-06 | open |
| 6 | Wire `sn-translator` into the *existing* old-stack Alertmanager (`webhook_config` in the `alertmanager-config` ConfigMap) so the chaos pipeline can run end-to-end on working infrastructure while CNI remediation is decided | me | 2026-06-02 | open |
| 7 | Drop the `k8s/kube-prometheus-stack/` HelmRelease file's `78.x → 86.x` bump commit forward; it's correct, it's just dormant. Add a note in `k8s/kube-prometheus-stack/README.md` flagging the CNI prerequisite | me | next attempt | open |

## Drift surfaced

Discovered while inspecting Grafana / pre-flighting the cutover. None
caused this incident — but worth recording because they were all
"working in a way nobody intended":

- `grafana-admin` Secret used `admin-password` key, but committed
  manifest referenced `password`. Fixed in commit `b991092`.
- Live Grafana env had `GF_SECURITY_ADMIN_PASSWORD=<plaintext>`
  inline (not from secretRef as the committed manifest claims).
  Password rotated post-discovery.
- Live Alertmanager Discord sidecar had
  `DISCORD_WEBHOOK_URL=REDACTED` as a literal inline value — meaning
  **Discord notifications haven't fired for the last ~63 days**.
  No real `alertmanager-discord` Secret has ever existed.
- `kubeStateMetrics`/`kube-state-metrics` values-key confusion in
  the kube-prom-stack chart (camelCase top level vs kebab-case
  subchart key). Misread as the latter; chart silently ignored.

## Lessons learned

- **Hidden brokenness is the worst kind.** A subsystem that's broken but
  not exercised is invisible until something new tries to use it. Build
  smoke tests for every subsystem you depend on — even the ones you
  "haven't touched in months." The cluster's pod-to-pod network is the
  poster child here.
- **`hostNetwork: true` is a strong signal of an underlying problem,
  not a feature.** Three components in `monitoring/monitoring.yml` use
  it, justified at the time as "for Tailscale connectivity." Looking
  back, it was working around a CNI failure that nobody had named.
- **ServiceMonitor-based observability tooling assumes pod-network
  health.** Most "modern" Kubernetes monitoring is incompatible with
  clusters that rely on hostNetwork. Pick a side: fix CNI before
  adopting tooling that depends on it, or accept a manual-scrape-config
  world.
- **A migration plan should include a connectivity precheck**, not just
  a state precheck. "Does the new system's networking assumptions hold?"
  is as important as "Do the prerequisites exist?"
- **Roll back fast when the underlying assumption is wrong.** We spent
  ~10 min realising the targets were unreachable, then a few minutes
  considering "patch the chart with hostNetwork everywhere" before
  deciding the patch is a rewrite, not a fix. Rolling back was the
  faster route to a working cluster.
