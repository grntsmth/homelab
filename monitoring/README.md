# monitoring/

Full observability stack, pinned to the `star-garden` worker node via `nodeSelector: role: watchtower`. All pods use `hostNetwork: true` and cross-component calls follow the same-node rules in [ADR-001](../docs/decisions/001-design-around-broken-pod-network.md) — Prometheus reaches Alertmanager at `localhost:9093`, and NodePort targets are always addressed on the node hosting the pod.

## What's deployed

| Component | Image | Exposed as |
|---|---|---|
| Prometheus | `prom/prometheus:v3.11.0` | NodePort 30090 |
| Grafana | `grafana/grafana:12.4.2` | NodePort 30300 |
| Alertmanager | `prom/alertmanager:v0.31.1` | localhost:9093 (hostNetwork; ClusterIP Service exists but delivery uses localhost) |
| Discord webhook relay | `python:3.12-slim` (inline script) | sidecar, localhost:9097 |
| node-exporter | `prom/node-exporter:v1.10.2` | DaemonSet, hostPort 9100 on every node |

## Scrape targets

Prometheus scrapes across the Tailscale mesh, so targets are keyed by Tailscale IP:

| Job | Target | Source |
|---|---|---|
| `prometheus` | `localhost:9090` | self |
| `node-high-palace` | `100.92.211.3:9100` | node-exporter DaemonSet |
| `node-star-garden` | `100.123.222.55:9100` | node-exporter DaemonSet |
| `terminal-windows` | `100.93.245.19:9182` | [windows_exporter](https://github.com/prometheus-community/windows_exporter) |
| `terminal-gpu` | `100.93.245.19:9835` | [nvidia_gpu_exporter](https://github.com/utkuozdemir/nvidia_gpu_exporter) |
| `kube-state-metrics` | `100.92.211.3:30082` | cluster object state (NodePort on the node hosting the pod — see the comment in `monitoring.yml`) |
| `kubelet-cadvisor-hp` | `100.92.211.3:10250` | container metrics (filtered) |
| `kubelet-cadvisor-sg` | `100.123.222.55:10250` | container metrics (filtered) |

The two kubelet cadvisor scrapes use `metric_relabel_configs` to keep only `container_memory_working_set_bytes`, `container_cpu_usage_seconds_total`, `container_memory_rss`, and `container_network_*`. Without this, Prometheus retention blows up on a 20 GB PVC.

### Private overlays

Workload-specific scrape jobs and alert rules live **outside this repo** and arrive via two optional ConfigMaps, mounted by the Prometheus deployment and picked up through `scrape_config_files` / `rule_files` globs:

- `prometheus-private-scrape` → `/etc/prometheus/scrape.d/*.yml`
- `prometheus-private-rules` → `/etc/prometheus/rules-private/*.yml`

This keeps `monitoring.yml` both fully public and fully deployable — no placeholder values, no post-apply editing, no private targets committed. If the ConfigMaps don't exist, the globs match nothing and the base stack runs standalone.

## Alerts

Groups in `alerts.yml`:

- **host-cpu** — per-node thresholds: the game-server node alerts at 95% sustained 15m (bursty workloads are normal there), the watchtower at 90%/10m (anything sustained is abnormal).
- **host-memory / host-disk** — 90%/5m warning, 85% disk critical.
- **host-availability** — `NodeExporterDown` (3m, critical) plus `TargetDown` covering every non-node job; kube-state-metrics was once down for weeks with no alert, never again.
- **alerting-path** — `NotificationDeliveryBroken` watches `prometheus_notifications_errors_total`. Delivery itself once failed silently for six weeks (see the [postmortem addendum](../docs/postmortems/2026-05-30-kube-prom-stack-cutover-rollback.md)); this can't page through a dead path, but it makes the failure loud on every dashboard and the Grafana alert list.

Routing: alerts labelled `team: infrastructure` go to ServiceNow via [sn-translator](../apps/sn-translator/) (`continue: true`, so they also reach Discord); criticals repeat hourly to Discord, warnings every 4h.

## Dashboards

Versioned in [`dashboards/`](dashboards/) and **provisioned** into Grafana from a ConfigMap — the repo copy is the live copy, not an export that drifts:

```bash
kubectl -n monitoring create configmap grafana-dashboards \
  --from-file=monitoring/dashboards/ --dry-run=client -o yaml | kubectl apply -f -
```

Grafana watches the provisioned folder; changes land on the next sync (or `rollout restart deploy/grafana`). Dashboards edited in the UI must be exported back into `dashboards/` or the reconcile overwrites them — that's the point.

## Secrets & environment config

Created out of band (never committed here):

```bash
# NOTE: the key is admin-password (matching monitoring.yml's secretKeyRef) —
# an earlier version of this doc said 'password', which bricks Grafana login.
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-password='...'

kubectl -n monitoring create secret generic alertmanager-discord \
  --from-literal=webhook-url='https://discord.com/api/webhooks/...'

# Real public URL for Grafana (committed manifest carries no domain):
kubectl -n monitoring create configmap grafana-env \
  --from-literal=GF_SERVER_ROOT_URL='https://<your-domain>/grafana/'
```

In this homelab, `grafana-admin` is additionally managed as a [Sealed Secret](https://github.com/bitnami-labs/sealed-secrets) committed to a private repo alongside the private overlay ConfigMaps; `alertmanager-discord` is plain out-of-band.

## What's intentionally not here

- **Remote write / long-term storage**: 30d local retention on a 20 GB PVC is enough for a homelab. No Thanos, no Cortex.
