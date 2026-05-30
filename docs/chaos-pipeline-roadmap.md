# Chaos Pipeline Roadmap

Sequenced follow-ups for the chaos engineering pipeline introduced in
`k8s/` and `sn-translator/`. Pipeline architecture is documented in
[`k8s/README.md`](../k8s/README.md).

## Phase 1 — Bring it green (this week)

The pipeline is built but nothing is running yet. Sequence matters here:

1. **Seal the ServiceNow credentials.** Run the `kubeseal` block in
   `k8s/sn-translator/sealed-secret.yml` against the cluster controller;
   commit the resulting ciphertext.
2. **Build + load the sn-translator image** on `high-palace`:
   `docker build` → `docker save | sudo k3s ctr images import -`. Mirrors
   the Chronicle deploy pattern.
3. **Decide on the kube-prometheus-stack migration window.** The pipeline
   assumes that migration is done. Two options:
   - Migrate now (tear down `monitoring/monitoring.yml`'s
     Alertmanager/Prometheus/Grafana, install the chart with the values
     in `k8s/alertmanager/helm-values-snippet.yml`) — clean cutover but
     more change in one sitting.
   - Apply only `sn-translator/` + `chaos-mesh/` now, leave
     `alertmanager/` + `prometheus-rules/` queued until the chart lands.
4. **Smoke test pod-kill end-to-end.** Apply the experiment, watch the
   timeline in `k8s/README.md`'s runbook. Confirm the incident appears
   in devXXXXXX *and* auto-resolves. First successful loop is the only
   thing that proves the pipeline really works.
5. **Document any field-mapping surprises** hit during smoke testing.
   The PDI quirks list in `sn-translator/config.py`
   (`NAMESPACE_TO_CATEGORY`) is a starter — more will surface on first
   contact.

## Phase 2 — Close the obvious gaps (next 2–4 weeks)

Things the build deliberately punted on:

1. **Stand up a blackbox-exporter Probe** targeting Chronicle's ingress.
   Until then `HighLatencyDetected` never fires and the `network-delay`
   experiment has no detection signal. The rule deploys cleanly without
   it, but the loop is open.
2. **First real postmortem.** After 2–3 chaos sessions there's enough
   raw material for a postmortem in `docs/postmortems/` — the homelab
   README already promises that surface and currently has zero entries.
3. **CI coverage for `k8s/`.** Extend `.github/workflows/validate.yml`
   to `kubeconform` the new directory with the datreeio CRD catalog so
   Flux / HelmRelease / PrometheusRule are recognised.
4. **FluxCD bootstrap.** The chaos pipeline is the first thing in the
   repo that's genuinely structured for GitOps. Bootstrapping Flux
   against `k8s/` (with the `chaos-experiments/` exclusion intact) is
   the natural moment to graduate off `kubectl apply`. Closes the
   "Lightweight GitOps controller" item in the README's "Currently
   exploring" list.
5. **Promote one experiment to a `Schedule` CR.** A weekly off-hours
   pod-kill against `ecosystem` proves the alerting still works even
   when no human is watching, and generates a steady drumbeat of
   postmortem material.

## Phase 3 — Portfolio maturity (1–3 months)

The chaos pipeline is most credible as portfolio material when it
generates real artefacts. Sequenced toward storytelling:

1. **A "chaos timeline" Grafana dashboard.** Three rows on one screen:
   chaos experiment status (from chaos-mesh's exported metrics),
   Alertmanager firing/resolved events, and a table of SN incident
   numbers. Single screenshot proves the whole loop. Commit to
   `monitoring/dashboards/` alongside `three-realms.json`.
2. **SLO definitions for sn-translator + Chronicle.** The homelab README
   explicitly calls out "no target reliability / no error-budget
   tracking" as a gap. Chaos engineering only earns its keep when error
   budget burn from a fault is observable. One-page SLO docs +
   multi-window burn-rate alerts (also a stated gap) is a natural
   Phase 3 deliverable.
3. **Runbook per chaos type.** `docs/runbooks/` currently has one
   entry. Each chaos experiment is a guaranteed-reproducible failure
   mode — writing the on-call response using the SN incident as a
   fixture is unusually high signal-to-effort.
4. **Make the public README aware this exists.** Right now nothing on
   the public homelab README mentions a chaos pipeline. A short
   "Reliability practices → Chaos engineering" subsection linking to
   `k8s/README.md` turns this from internal infra into a portfolio
   surface.

## Out of scope (for now)

- Multi-cluster, self-service chaos workflows, custom Workflow CR
  templates, change-management integration — all valid eventually, but
  at single-operator scale the marginal portfolio value drops off fast
  compared to **doing the loop end-to-end on real failures and writing
  it up**.
- Replacing the SQLite fingerprint store with Postgres. SQLite on a
  1Gi PVC is fine until many simultaneous chaos sessions are running,
  which won't happen at this scale.
