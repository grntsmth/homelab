# platform/

Core ingress layer: Traefik with auto-TLS via Let's Encrypt, running as the default k3s ingress controller.

## Files

| File | Purpose |
|---|---|
| `traefik-config.yml` | `HelmChartConfig` overriding the bundled k3s Traefik chart: enables persistent ACME storage, HTTP→HTTPS redirect, Let's Encrypt resolver. |
| `traefik-routes-example.yml` | Sanitized example IngressRoutes for Grafana + Prometheus, demonstrating the cross-namespace routing pattern. |

## The cross-namespace pattern

Traefik CRD `IngressRoute` objects cannot reference Services in other namespaces. The workaround used here:

1. Create a bare `Service` (no selector) + matching `Endpoints` object in `kube-system`, pointing to the worker node's internal IP and the target NodePort.
2. Reference that Service from the `IngressRoute`.

This keeps Traefik's routing table simple and lets real pods live wherever makes sense (monitoring on `role=watchtower`, apps on the control-plane node).

## Apply

```bash
kubectl apply -f traefik-config.yml
# wait for the k3s HelmChartConfig reconciler to roll Traefik
kubectl apply -f traefik-routes-example.yml
```

The `HelmChartConfig` change is picked up automatically by k3s; no manual Helm commands needed.

## Secrets

`traefik-routes-example.yml` references a `prometheus-auth-secret` for basic-auth gating of Prometheus. Create it out of band (not committed):

```bash
htpasswd -nbB admin "$(read -rs -p 'password: '; echo "$REPLY")" \
  | kubectl create secret generic prometheus-auth-secret \
      -n kube-system --from-file=users=/dev/stdin
```

In this homelab, all runtime secrets are managed via [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) so they can be committed encrypted. The example above omits that step for clarity.
