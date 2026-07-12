# ADR-002: Flux helm-controller without Git repo sync

**Date:** 2026-07-12
**Status:** accepted

## Context

Flux controllers (source, kustomize, helm, notification) were installed
during the chaos-pipeline build. The original plan wired a GitRepository +
Kustomization sync over the manifest tree (`clusters/homelab/flux-sync.yml`,
shipped suspended). That sync was never unsuspended — and then the
kube-prometheus-stack migration it was gated on rolled back
([postmortem](../postmortems/2026-05-30-kube-prom-stack-cutover-rollback.md)).

Meanwhile ArgoCD had already been trialled twice in a sibling project and
retired both times: at single-operator scale, reconciler overhead and
drift-fighting cost more than drift-detection earned. The same argument
applies to a full Flux sync here — this lab makes frequent ad-hoc live
edits by design (it's a learning environment), and a pruning reconciler
turns every experiment into a fight.

## Decision

- **helm-controller stays** and owns Helm chart lifecycles from
  HelmRelease/HelmRepository CRs applied with `kubectl apply` (today:
  chaos-mesh, from `chaos/chaos-mesh/`). Declarative chart management
  with none of the repo-sync friction.
- **No GitRepository/Kustomization sync.** Plain manifests reach the
  cluster via `kubectl apply -f`, and the repo is kept deployable-as-
  committed (no placeholder values; environment-specifics arrive via
  out-of-band ConfigMaps/Secrets documented per component).
- `clusters/` and the suspended flux-sync manifest were removed from the
  repo. The flux-system controllers are cluster infrastructure, installed
  via `flux install`.

## Operational notes

- helm-controller and notification-controller are pinned to the
  control-plane node (`kubernetes.io/hostname=high-palace`) — they must
  reach source-controller and CoreDNS, both of which sit there, and
  cross-node pod traffic doesn't work (ADR-001). **This pin is a live
  patch, not in git**; re-apply after any `flux install` upgrade:

  ```bash
  kubectl -n flux-system patch deploy helm-controller notification-controller \
    --type merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"high-palace"}}}}}'
  ```

## Consequences

- "GitOps" claims in this repo mean exactly: HelmReleases are declarative
  and reconciled; manifests are versioned but applied imperatively. The
  README says this plainly instead of overpromising.
- Revisit trigger: same as ADR-001's — a CNI fix plus a real need for
  drift detection (e.g. a second operator).
