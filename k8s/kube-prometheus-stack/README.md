# kube-prometheus-stack

FluxCD-managed Helm release for the cluster's metrics + alerting +
dashboards. Replaces the handwritten Prometheus + Alertmanager +
Grafana + node-exporter Deployments in `monitoring/monitoring.yml`
during the Phase 1.3 migration.

## Layout

```
k8s/kube-prometheus-stack/
├── README.md
├── helmrepository.yml         # source: prometheus-community chart repo
├── helmrelease.yml            # chart + values (~250 lines)
├── dashboards/
│   └── three-realms.json      # versioned dashboard, provisioned via sidecar
└── kustomization.yml          # generates labelled ConfigMap for the sidecar
```

The `dashboards/three-realms.json` file is a copy of
`monitoring/dashboards/three-realms.json`. The original will be deleted
during the migration cutover commit — kustomize's
`configMapGenerator` can't load files from outside the kustomization
tree without `--load-restrictor=LoadRestrictionsNone`, and Flux's
Kustomization spec doesn't expose that flag, so the file lives here.

## Pre-apply checklist (one-time)

1. **Add the `admin-user` key to the `grafana-admin` Secret.** The chart
   expects both `admin-user` and `admin-password`; you currently only
   have the password:

   ```bash
   kubectl -n monitoring patch secret grafana-admin \
     -p '{"data":{"admin-user":"YWRtaW4="}}'
   # YWRtaW4= is base64 for "admin"
   ```

2. **Confirm the alertmanager Secret is in place.** The HelmRelease
   references `alertmanager-chaos-config` via `configSecret`. If that
   Secret doesn't exist when the chart reconciles, the Alertmanager pod
   will CrashLoopBackOff:

   ```bash
   kubectl -n monitoring get secret alertmanager-chaos-config
   ```

3. **Confirm the chaos PrometheusRules are in place.** The chart's
   Prometheus picks them up via the `release: kube-prometheus-stack`
   label selector:

   ```bash
   kubectl -n monitoring get prometheusrule -l release=kube-prometheus-stack
   ```

## Migration cutover order

This is the high-stakes block of Phase 1.3. The window between teardown
and chart readiness is when alerting is offline.

```bash
# 1. Confirm prereqs (above)

# 2. Tear down the handwritten stack (keep PVCs, Secrets, IngressRoutes).
kubectl -n monitoring delete deploy prometheus alertmanager grafana
kubectl -n monitoring delete configmap prometheus-config alertmanager-config
kubectl -n monitoring delete daemonset node-exporter
# Old NodePort services — DELETE so chart can claim the ports cleanly.
kubectl -n monitoring delete svc prometheus grafana

# 3. Apply this directory (Flux will do this automatically if you've
#    already unsuspended the Kustomization; otherwise:)
kubectl apply -k k8s/kube-prometheus-stack/

# 4. Watch the chart come up. Expect ~3-5 min for all pods Ready.
kubectl -n monitoring get pods -w

# 5. Apply the chaos pipeline pieces that depend on the chart being up.
kubectl apply -k k8s/alertmanager/
kubectl apply -k k8s/prometheus-rules/

# 6. Unsuspend Flux now that prereqs exist:
flux resume kustomization homelab-k8s -n flux-system
```

## What the chart provides vs what stays external

| Component | Source | Notes |
|---|---|---|
| Prometheus | chart | NodePort 30090, retention 30d, 20Gi PVC |
| Alertmanager | chart | configSecret = `alertmanager-chaos-config` |
| Grafana | chart | NodePort 30300, dashboards from sidecar |
| node-exporter DaemonSet | chart | replaces existing — delete old before apply |
| kube-state-metrics | **external** | already in kube-system from private ops repo; chart's copy disabled to avoid duplicate scrape |
| Loki + Promtail | **external** | unchanged; chart wires Loki as a datasource via cluster DNS |
| Discord relay | **external** | `k8s/alertmanager/discord-relay.yml` (standalone Deployment, not a sidecar) |

## Ingress

NodePorts 30090 and 30300 are deliberately reused so the existing
`grafana` and `prometheus` IngressRoutes in `kube-system` (referencing
the worker node IP at those ports) keep working without changes. If you
ever need a fresh IngressRoute pattern, see
`platform/traefik-routes-example.yml`.

## Pinning policy

Chart version is pinned to `86.x` — semver patch tolerance, no
auto-major-upgrade. Bumping to a new major (e.g. 87.x) is a deliberate
edit + commit, not a Flux auto-pull, because chart majors occasionally
rename values keys.

## Reference superseded

`k8s/alertmanager/helm-values-snippet.yml` is now superseded by this
HelmRelease. It stays in the tree as the "minimum viable" reference for
anyone bringing up the chart by hand outside Flux.
