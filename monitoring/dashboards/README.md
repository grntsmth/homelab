# Grafana dashboards

Dashboards in this directory are exported from the running Grafana on `star-garden` and versioned alongside the manifests that produce the metrics they visualize.

## Dashboards

| File | UID | Title |
|---|---|---|
| `three-realms.json` | `three-realms` | Fortress Infrastructure — Three Realms |

### `three-realms.json`

Single-pane infra overview for all three nodes (`high-palace`, `star-garden`, `terminal`). Panels include:

- Per-node CPU, memory, and disk gauges
- Available-resource stats (free RAM/CPU/disk)
- GPU temperature, utilization, VRAM, power (terminal / RTX 5070 Ti)
- Time series: CPU, memory, GPU temp + power, GPU util + VRAM, disk usage, network RX, I/O wait, disk I/O time %
- Kubernetes: pods running, pods by namespace, pod restarts (1h)
- Prometheus: target count, scrape duration
- Per-component memory and CPU breakdown for High Palace and Star Garden (top containers, stacked + bargauge)

Schema version 42 (Grafana 12.x).

## Importing

The exported JSON has hard-coded datasource UIDs from the source Grafana instance. On import into a fresh Grafana:

1. *Dashboards → New → Import → Upload JSON file*.
2. When prompted, remap each Prometheus datasource selector to the local Prometheus datasource.
3. Save.

If you'd rather avoid the remap step, replace the literal datasource UIDs in the JSON with a template variable (`${DS_PROMETHEUS}`) and add a matching `datasource` templating list entry. Not done here because this dashboard is exported for showcase, not redistribution.

## What's intentionally not here

- **The Minecraft Server dashboard.** It's specific to the private operations repo and isn't relevant to the public infrastructure showcase.
- **Per-application SLO dashboards.** None exist yet — see the *Service Level Objectives* section of the top-level README.
