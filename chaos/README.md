# Chaos Engineering Pipeline

A closed-loop pipeline that wires a Chaos Mesh experiment all the way
through to a ServiceNow incident and back to resolution — modelling the
incident lifecycle the same way a production IT operations team would
run it.

## Why this exists

The homelab already has Prometheus, Alertmanager, and Grafana. What it
was missing was the back half of an incident lifecycle: ticketing,
triage state, and post-incident review surface. Plumbing this pipeline
gives me the same shape of artefacts a regulated-bank operations team
relies on — Change Number, Resolution Code, MTTR — without inventing
fake incidents. The faults are real (Chaos Mesh kills real pods); the
ticket is real (ServiceNow PDI); the only thing simulated is the
business impact.

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  k3s cluster (Tailscale mesh)                                      │
│                                                                    │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│  │ Chaos Mesh  │ ─▶ │ Workload pods   │ ─▶ │ Prometheus       │    │
│  │ (PodChaos,  │    │ (ecosystem ns)  │    │ (kube-prom-stack)│    │
│  │  Network,   │    │  - chronicle    │    │  + PrometheusRule│    │
│  │  Stress)    │    │  - ollama-relay │    │                  │    │
│  └─────────────┘    └─────────────────┘    └────────┬─────────┘    │
│        ▲                                            │              │
│        │ kubectl apply                              ▼              │
│        │                                   ┌──────────────────┐    │
│        │                                   │ Alertmanager     │    │
│        │                                   │ (routes by label)│    │
│        │                                   └────┬────────┬────┘    │
│        │                                        │        │         │
│        │                              ┌─────────▼──┐   ┌─▼──────┐  │
│        │                              │ Discord    │   │ sn-    │  │
│        │                              │ webhook    │   │ trans- │  │
│        │                              │ sidecar    │   │ lator  │  │
│        │                              └────────────┘   └───┬────┘  │
│                                                            │       │
└────────────────────────────────────────────────────────────┼───────┘
                                                             │ httpx
                                                             ▼
                                            ┌─────────────────────────┐
                                            │ ServiceNow PDI          │
                                            │ devXXXXXX.service-now   │
                                            │ POST /api/now/table/    │
                                            │      incident           │
                                            └─────────────────────────┘
```

### Lifecycle

1. **Inject** — `kubectl apply` a Chaos Mesh resource (PodChaos, NetworkChaos, StressChaos).
2. **Detect** — A `PrometheusRule` evaluates the resulting symptom every 30s.
3. **Page** — Alertmanager routes any alert with `chaos_type=*` *or*
   (`severity=critical` + `team=infrastructure`) to the `servicenow` receiver
   while continuing to fan out to Discord.
4. **Ticket** — `sn-translator` translates the Alertmanager webhook into a
   ServiceNow incident, mapping severity → urgency/impact, namespace →
   category, and stashing the alert `fingerprint → sys_id` in SQLite for
   later closure.
5. **Recover** — Chaos Mesh experiment expires (or is deleted), Prometheus
   stops firing, Alertmanager emits a `resolved` webhook.
6. **Close** — sn-translator looks up the fingerprint and PATCHes the
   incident to state=Resolved with a close note pointing at the original
   fingerprint and endsAt timestamp.

### Field mapping quirks

`category="infrastructure"` is silently rejected on a fresh PDI (it isn't
in the OOB choice list). `sn-translator/translator.py` maps it to
`"inquiry"` along with a handful of other namespace → category translations.
The mapping table is `NAMESPACE_TO_CATEGORY` in `sn-translator/config.py` —
edit there if you add a new namespace.

## Directory layout

```
k8s/
├── kustomization.yml          # top-level Flux entrypoint (excludes chaos-experiments)
├── sn-translator/             # FastAPI translator deployment
│   ├── deployment.yml         # + liveness/readiness on /health
│   ├── service.yml            # ClusterIP :8091 in ecosystem ns
│   ├── sealed-secret.yml      # PLACEHOLDER — must be re-sealed locally
│   └── kustomization.yml
├── alertmanager/              # Alertmanager config Secret (kube-prom-stack shape)
│   ├── alertmanager-config.yml    # Secret: alertmanager-chaos-config
│   ├── discord-relay.yml          # Standalone Discord webhook relay (was a sidecar)
│   ├── helm-values-snippet.yml    # Reference: kube-prom-stack values needed
│   └── kustomization.yml
├── chaos-mesh/                # Flux HelmRelease for Chaos Mesh
│   ├── namespace.yml          # privileged PSA labels
│   ├── helmrelease.yml        # dashboard off, containerd socket wired
│   └── kustomization.yml
├── chaos-experiments/         # NOT included in top-level kustomization
│   ├── pod-kill.yml           # PodChaos — kill one ecosystem pod
│   ├── network-delay.yml      # NetworkChaos — 200–500ms egress for 2m
│   ├── cpu-stress.yml         # StressChaos — 80% CPU on game-server for 90s
│   └── kustomization.yml
└── prometheus-rules/          # PrometheusRule for chaos detection
    ├── chaos-rules.yml        # KubePodNotRunning + HighLatency + NodeCPUPressure
    └── kustomization.yml
```

The `sn-translator/` Python source lives at `../sn-translator/` (sibling
to `k8s/`).

## Wiring into kube-prometheus-stack

This pipeline assumes you've installed (or are installing) the
`kube-prometheus-stack` Helm chart with release name `kube-prometheus-stack`
in the `monitoring` namespace. Two values must be set so the chart picks up
the Alertmanager config in this directory instead of generating its own:

```yaml
# k8s/alertmanager/helm-values-snippet.yml has the full block; the
# load-bearing two settings are:
alertmanager:
  config: null                                      # suppress chart-generated Secret
  alertmanagerSpec:
    configSecret: alertmanager-chaos-config         # point at ours instead
```

Without those two lines, the chart creates its own
`alertmanager-kube-prometheus-stack-alertmanager` Secret on every release
and the Operator-managed Alertmanager pod will never load this routing
config. The Secret in `alertmanager-config.yml` is deliberately named
`alertmanager-chaos-config` so there's no name collision either way.

`prometheus.prometheusSpec.ruleSelector` also needs to match the
`release: kube-prometheus-stack` label on `prometheus-rules/chaos-rules.yml`
— again, see the snippet file for the full block.

### Migration order

When cutting over from your existing handwritten Prometheus
(`monitoring/monitoring.yml`) to kube-prometheus-stack:

1. **Apply this directory first** while the old stack is still serving alerts.
   The Discord relay Deployment, ServiceNow translator, and PrometheusRule
   all deploy cleanly without the chart present.
2. **Delete the old Alertmanager+Prometheus+Grafana** Deployments from
   `monitoring/monitoring.yml` (keep the node-exporter DaemonSet — the
   chart's `nodeExporter` should be disabled to avoid duplicates).
3. **Install kube-prometheus-stack** with the values from
   `alertmanager/helm-values-snippet.yml`. The new Alertmanager will
   come up pre-loaded with the chaos routing.
4. **Verify** with the pre-flight checks in the runbook below.

## Sealing the ServiceNow credentials

The committed `k8s/sn-translator/sealed-secret.yml` contains a placeholder.
Before the translator can authenticate to ServiceNow, replace it with a
locally-sealed copy:

```bash
kubectl -n ecosystem create secret generic sn-translator-credentials \
  --from-literal=SN_USER='REDACTED_USER' \
  --from-literal=SN_PASSWORD='<paste real PDI password>' \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace=kube-system \
           --controller-name=sealed-secrets-controller \
           --format=yaml \
> k8s/sn-translator/sealed-secret.yml
```

`SN_INSTANCE` stays in the Deployment manifest as plain config — it's
the public PDI URL, not a secret.

## Building the translator image (ARM64)

The Dockerfile uses `python:3.12-slim` which publishes multi-arch
manifests including `linux/arm64/v8`, so the build runs natively on
the OCI A1.Flex nodes:

```bash
cd sn-translator
docker build -t sn-translator:latest .

# Load into k3s containerd (cluster doesn't pull from a registry):
docker save sn-translator:latest \
  | sudo k3s ctr images import -

# Rollout:
kubectl -n ecosystem rollout restart deployment/sn-translator
```

## Chaos Runbook

> Before running any experiment in a session, post in `#homelab-alerts`
> that you're running chaos and link to this runbook. The Discord
> sidecar will fire on every PrometheusRule trip — labelling the
> session up front prevents an actual on-call response.

### Pre-flight (every session)

```bash
# 1. Confirm sn-translator is healthy and can reach ServiceNow.
kubectl -n ecosystem exec deploy/sn-translator -- \
  curl -s http://localhost:8091/health
# expect: {"status":"ok","servicenow_reachable":true,"instance":"devXXXXXX.service-now.com"}

# 2. Confirm Chaos Mesh controller is up.
kubectl -n chaos-mesh get pods

# 3. Confirm Prometheus has loaded the chaos rules.
kubectl -n monitoring exec sts/prometheus-kube-prometheus-stack-prometheus -c prometheus -- \
  wget -qO- http://localhost:9090/api/v1/rules \
  | grep -E 'KubePodNotRunning|HighLatencyDetected|NodeCPUPressure'
```

### Experiment 1 — Pod kill

```bash
kubectl apply -f k8s/chaos-experiments/pod-kill.yml

# Watch in real time:
kubectl -n ecosystem get pods -w &
kubectl -n monitoring port-forward svc/alertmanager 9093:9093 &
open http://localhost:9093

# Expected timeline:
#  t+0s    : pod-kill applied, target pod terminating
#  t+5s    : kube-state-metrics observes new pod in non-Running phase
#  t+1m    : KubePodNotRunning fires (PrometheusRule `for: 1m`)
#  t+~70s  : Alertmanager group_wait elapses, webhook sent to sn-translator
#  t+~75s  : ServiceNow incident created — confirm in devXXXXXX UI
#  t+~90s  : pod back in Running phase, alert resolves
#  t+~95s  : sn-translator closes the incident, state=Resolved
```

### Experiment 2 — Network latency

```bash
kubectl apply -f k8s/chaos-experiments/network-delay.yml

# 2-minute experiment. HighLatencyDetected only fires if you have a
# blackbox probe pointed at ecosystem services — see "Adding a latency
# probe" below if the alert never trips.

# Cleanup (the duration field auto-expires it, but you can also delete):
kubectl delete -f k8s/chaos-experiments/network-delay.yml
```

### Experiment 3 — CPU stress

```bash
kubectl apply -f k8s/chaos-experiments/cpu-stress.yml

# 90-second experiment on high-palace. Watch in Grafana — the
# "Fortress Infrastructure — Three Realms" dashboard's CPU panel
# for high-palace should spike to ~80%.

# NodeCPUPressure has `for: 2m` so brief experiments may not trip it;
# extend the StressChaos `duration` to 3m if you want guaranteed firing.
```

### Manual incident closure (when an experiment is interrupted)

If you ctrl-C an experiment and the alert clears before Alertmanager
sends a `resolved` payload, sn-translator's SQLite store will still
hold the open fingerprint. Close it by hand:

```bash
# Find the fingerprint:
kubectl -n ecosystem exec deploy/sn-translator -- \
  sqlite3 /data/incidents.db \
  "SELECT fingerprint, number, alertname FROM incidents WHERE resolved_at IS NULL;"

# Close in ServiceNow UI, then mark resolved locally:
kubectl -n ecosystem exec deploy/sn-translator -- \
  sqlite3 /data/incidents.db \
  "UPDATE incidents SET resolved_at = datetime('now') WHERE fingerprint = '<paste>';"
```

### Post-incident review

After every chaos session:

1. Export the ServiceNow incident as a PDF.
2. Capture Grafana's "Three Realms" dashboard for the experiment window.
3. Write a short note under `docs/postmortems/` answering:
   - Did the alert fire within the expected window?
   - Did the incident contain enough context to triage without
     pulling kubectl logs?
   - Did closure happen automatically, or did the operator have to
     intervene? If intervene — why?

## Adding a latency probe (optional)

`HighLatencyDetected` expects `probe_http_duration_seconds_bucket` from
prometheus-community's blackbox-exporter. To wire one up:

```bash
helm install blackbox prometheus-community/prometheus-blackbox-exporter \
  -n monitoring --create-namespace=false
```

Then add a `Probe` CR targeting your ecosystem ingresses — see
[blackbox-exporter docs](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/api-reference/api.md#probe).
Until then, the rule deploys cleanly and simply never fires.

## Validation

CI validates the manifests with `kubeconform`:

```bash
kubeconform -strict -summary \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{ .Group }}/{{ .ResourceKind }}_{{ .ResourceAPIVersion }}.json' \
  k8s/
```

The Chaos Mesh and Flux CRD schemas are pulled from the datreeio catalog
so `kubeconform` recognises the custom kinds.

## What this is *not*

- **Not** a load-test rig. Chaos Mesh injects faults, not traffic.
- **Not** a replacement for the existing Discord alert path — both
  receivers fire (`continue: true`) so a chaos-triggered alert reaches
  Discord AND ServiceNow.
- **Not** safe to apply `chaos-experiments/` on a Flux reconcile loop —
  the directory is deliberately excluded from `k8s/kustomization.yml`.
