# Grafana dashboards

Dashboards in this directory are **provisioned** into the running Grafana — the repo copy is the live copy. Grafana loads every JSON here from the `grafana-dashboards` ConfigMap via the file provider in `monitoring.yml` (`grafana-dashboard-provider`).

## Dashboards

| File | UID | Title |
|---|---|---|
| `three-realms.json` | `three-realms` | Three Realms — Infrastructure Overview |
| `platform-health.json` | `platform-health` | Platform Health — Alerting, Targets & Data Safety |
| `ecosystem-slo.json` | `ecosystem-slo` | Ecosystem Services — SLO |

### `three-realms.json`

Single-pane infra overview for all three nodes (`high-palace`, `star-garden`, `terminal`): per-node CPU/memory/disk gauges, GPU temperature/utilization/VRAM/power, Kubernetes pod counts and restarts, Prometheus scrape health, per-component memory/CPU breakdowns.

### `platform-health.json`

The meta-dashboard: is the monitoring itself working? Alerting-path row (notification sent/error counters — the exact signal that would have caught a six-week silent delivery failure), Alertmanager deliveries by receiver, scrape-target health, Traefik request rates + p95 latency + TLS cert expiry, CronJob backup freshness, failed Jobs.

### `ecosystem-slo.json`

The 99%/30d availability SLO for the ecosystem services: per-instance availability, error-budget remaining, 1h/6h burn rates against the 14.4×/6× alert thresholds, probe latency and status codes. Fed by blackbox-exporter probes and the `slo:probe_availability:*` recording rules.

## Deploying changes

```bash
kubectl -n monitoring create configmap grafana-dashboards \
  --from-file=monitoring/dashboards/ --dry-run=client -o yaml | kubectl apply -f -
kubectl -n monitoring rollout restart deploy/grafana
```

Dashboards edited in the Grafana UI must be exported back here (bump the JSON `version`) or the next reconcile overwrites the edit — that is the intended direction of truth. CI checks every file parses and UIDs stay unique.

## What's intentionally not here

- **Private workload dashboards.** They live in the private operations repo.
- **Datasource templating.** JSONs carry the instance's Prometheus datasource UID directly; on a foreign Grafana, remap on import.
