# clusters/homelab

Flux entry-point for the OCI k3s cluster. Contains the GitRepository +
Kustomization CRs that tell Flux where to pull from and what to reconcile.

## Layout

```
clusters/homelab/
├── README.md
└── flux-sync.yml   # GitRepository + Kustomization for ./k8s
```

The `flux-system/` directory that a full `flux bootstrap` would create
is intentionally absent — Flux controllers were installed via
`flux install` (not via the bootstrap flow) so they're not self-managing
through this repo. That's deliberate: keeps push control with the
operator and avoids committing Flux's auto-generated component manifests.

## One-time setup

`flux install` must already have run against the cluster. Verify with
`flux check`.

Then, once this file is committed *and pushed* to the repo's `main`
branch:

```bash
kubectl apply -f clusters/homelab/flux-sync.yml
```

This is the only `kubectl apply` you should ever need against this
cluster for declarative state — everything else gets reconciled by
the Flux Kustomization.

## Suspended-until-prerequisite gate

`flux-sync.yml` ships with `spec.suspend: true` on the Kustomization
because `k8s/chaos-mesh/helmrelease.yml` creates a `PodMonitor`, which
is a CRD owned by kube-prometheus-stack. Reconciling before
kube-prometheus-stack is installed puts chaos-mesh into a retry loop.

When kube-prometheus-stack is in place (Phase 1.3 step 5), unsuspend:

```bash
flux resume kustomization homelab-k8s -n flux-system
```

Confirm reconcile started:

```bash
flux get kustomization homelab-k8s
flux logs --kind=Kustomization --name=homelab-k8s -f
```

## Adding more sources

For each additional repo or chart source Flux should watch (e.g. when
kube-prometheus-stack lands as its own HelmRelease pointing at the
prometheus-community Helm repo), drop a new manifest in this directory.
Stay disciplined: every GitRepository / HelmRepository / Kustomization
the cluster trusts should be declared here, not applied ad-hoc.
