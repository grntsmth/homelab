# CoreDNS DNS resolution fails after node reboot

**Severity:** critical
**Pages:** Discord (`#alerts`) when downstream services start failing scrape — there is no direct CoreDNS-down alert today (see *Prevention*).
**First seen:** Phase-10 multi-node bring-up (Tailscale mesh + monitoring migration to `star-garden`).
**Related alerts:** none direct. Symptoms surface as `NodeExporterDown` for Tailscale-IP scrape targets, or as application logs full of `lookup foo on 10.43.0.10:53: no such host`.

## Symptoms

After a node reboot — typically `high-palace` or `star-garden` coming back from OCI maintenance, kernel update, or a manual reboot:

- Pods on the rebooted node cannot resolve cluster-internal or external hostnames.
- Application logs show `dial tcp: lookup <name>: no such host` or `i/o timeout` against `10.43.0.10:53` (the default k3s CoreDNS service ClusterIP).
- `kubectl exec -n monitoring deploy/prometheus -- nslookup grafana` times out or returns `;; connection timed out; no servers could be reached`.
- The cluster itself looks healthy (`kubectl get nodes` is `Ready`, CoreDNS pods are `Running`).

## Likely causes

In historical frequency order in this homelab:

1. **CoreDNS upstream is `100.100.100.100` (Tailscale MagicDNS), which is unreachable from inside the pod network until Tailscale finishes coming up post-reboot.** The k3s default CoreDNS Corefile was previously patched to forward unknown queries to MagicDNS so pods could resolve Tailscale hostnames (`star-garden`, `high-palace`, `terminal`). On a clean boot, CoreDNS starts before Tailscale establishes routes, so the upstream is dead, and pods get NXDOMAIN or timeout for every lookup that escapes the cluster zone.
2. (Less common) `tailscaled` itself didn't come back — `systemctl status tailscaled` is `inactive` or `failed`. Resolves separately from this runbook.

## Diagnostic steps

Run from the operator workstation, with kubeconfig pointed at the homelab cluster.

```bash
# 1. CoreDNS itself running?
kubectl -n kube-system get pods -l k8s-app=kube-dns

# 2. From a known-good pod, query CoreDNS directly. If this hangs, the upstream is the problem.
kubectl -n monitoring exec deploy/prometheus -- nslookup kubernetes.default

# 3. Inspect the live Corefile. The "forward . <addr>" line is the upstream.
kubectl -n kube-system get configmap coredns -o yaml | grep -A2 'forward'

# 4. On the affected node, confirm Tailscale is up.
ssh <node> 'tailscale status | head -3'
```

If step 3 shows `forward . 100.100.100.100` (or similar MagicDNS address), that's the cause.

## Mitigation

Restoring service does **not** require a CoreDNS restart — just a Corefile edit and a re-roll. Replace the broken forward line with a stable upstream chain:

```bash
kubectl -n kube-system edit configmap coredns
```

In the `Corefile` block, change:

```
forward . 100.100.100.100
```

to:

```
forward . 169.254.169.254 8.8.8.8 1.1.1.1
```

(`169.254.169.254` is the OCI instance-metadata DNS, always reachable from inside the OCI VCN. `8.8.8.8` and `1.1.1.1` are public fallbacks.)

Then re-roll CoreDNS so it picks up the new config:

```bash
kubectl -n kube-system rollout restart deployment/coredns
kubectl -n kube-system rollout status deployment/coredns
```

Validate from a pod:

```bash
kubectl -n monitoring exec deploy/prometheus -- nslookup kubernetes.default
kubectl -n monitoring exec deploy/prometheus -- nslookup your-domain.example.com
```

Both should return answers within a second.

## Root-cause fix

The `forward .` line in the CoreDNS ConfigMap is now permanently set to the OCI/Google/Cloudflare chain. The Tailscale MagicDNS forwarder was removed because no in-cluster pod needs to resolve Tailscale hostnames — pods that talk to Tailscale peers (Prometheus scraping `terminal`, etc.) address them by IP directly.

Additionally, the platform pods in `monitoring/monitoring.yml` (Prometheus, Grafana, Alertmanager) set their own `dnsPolicy: None` and `dnsConfig.nameservers` to the same chain. This keeps the monitoring stack resolving even during a CoreDNS rollout window:

```yaml
dnsPolicy: None
dnsConfig:
  nameservers:
    - 169.254.169.254
    - 8.8.8.8
    - 1.1.1.1
```

(See `monitoring/monitoring.yml` — applied to the Prometheus, Grafana, and Alertmanager deployment templates.)

## Prevention

- **Missing alert: CoreDNS resolution failure.** A `probe_success`-style synthetic DNS lookup against the CoreDNS service, alerting on failure for >2m, would catch this without waiting for a downstream service to break. Tracked as a TODO against the monitoring stack — would need a blackbox-exporter deployment, which doesn't exist in this repo yet.
- **Missing alert: Tailscale daemon status.** `tailscaled.service` health is not currently scraped. A `node_systemd_unit_state{name="tailscaled.service",state="active"}` lookup via node-exporter's systemd collector would surface tailscaled flaps before CoreDNS does.
- The platform-pod-level `dnsConfig` override pattern is worth applying to any new monitoring or platform workload that must keep running during a CoreDNS incident.
