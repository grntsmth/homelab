# monitoring/

Full observability stack, pinned to the `star-garden` worker node via `nodeSelector: role: watchtower`. All pods use `hostNetwork: true` so they can scrape Tailscale IPs directly — pod-to-Tailscale routing isn't reliable under flannel VXLAN in this setup.

## What's deployed

| Component | Image | Exposed as |
|---|---|---|
| Prometheus | `prom/prometheus:v3.11.0` | NodePort 30090 |
| Grafana | `grafana/grafana:12.4.2` | NodePort 30300 |
| Alertmanager | `prom/alertmanager:v0.31.1` | ClusterIP 9093 |
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
| `kube-state-metrics` | `100.123.222.55:30082` | cluster object state |
| `kubelet-cadvisor-hp` | `100.92.211.3:10250` | container metrics (filtered) |
| `kubelet-cadvisor-sg` | `100.123.222.55:10250` | container metrics (filtered) |

The two kubelet cadvisor scrapes use `metric_relabel_configs` to keep only `container_memory_working_set_bytes`, `container_cpu_usage_seconds_total`, `container_memory_rss`, and `container_network_*`. Without this, Prometheus retention blows up on a 20 GB PVC.

## Alerts

Grouped into `host-health`: high CPU / memory / disk, node-exporter down. Alertmanager routes critical alerts to Discord with a 1 hour repeat interval; warnings repeat every 4 hours. The Discord translator is a 40-line inline Python sidecar — simpler than bringing in a full webhook proxy image.

## What's intentionally not here

- **Dashboards**: I keep them in Grafana itself rather than the repo. `grafana-data` is a PVC, so dashboards survive pod restarts. Exporting them as ConfigMaps and reconciling is a FluxCD-era problem.
- **Workload-specific alerts**: this repo is the platform layer. Application teams (including my own private workloads) ship their own PrometheusRules.
- **Remote write / long-term storage**: 30d local retention on a 20 GB PVC is enough for a homelab. No Thanos, no Cortex.

## Secrets

`monitoring.yml` references two Kubernetes secrets that must be created separately (not committed):

```bash
kubectl create secret generic grafana-admin -n monitoring \
  --from-literal=password='...'

kubectl create secret generic alertmanager-discord -n monitoring \
  --from-literal=webhook-url='https://discord.com/api/webhooks/...'
```

In this homelab, both are sealed via [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) and committed in encrypted form to a separate private repo.
