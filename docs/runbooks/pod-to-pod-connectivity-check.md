# Runbook: pod-to-pod connectivity check

**When to run:** before adopting anything that assumes pod-network health
(ServiceMonitors, operators, sidecar meshes), after any k3s upgrade or CNI
change, and whenever a new cross-component failure smells like networking.

**Background:** on this cluster, direct pod-to-pod TCP is broken at every
distance while ClusterIP and hostNetwork paths work — see
[ADR-001](../decisions/001-design-around-broken-pod-network.md) and the
[2026-05-30 postmortem](../postmortems/2026-05-30-kube-prom-stack-cutover-rollback.md).
This check exists because that breakage stayed invisible for 63 days and
then cost a migration window. Two minutes of canary beats an evening of
rollback.

## The check

Start a listener pod (pin it to a node so you know the topology):

```bash
kubectl run cn-server --image=busybox:1.36 --restart=Never \
  --overrides='{"spec":{"nodeSelector":{"kubernetes.io/hostname":"high-palace"}}}' \
  --command -- sh -c "while true; do nc -l -p 8080; done"
kubectl wait --for=condition=Ready pod/cn-server --timeout=60s
SIP=$(kubectl get pod cn-server -o jsonpath='{.status.podIP}')
```

Probe it from a client pod — same node first, then repeat with the
nodeSelector set to another node for the cross-node case. The second probe
(kube-dns ClusterIP) is the positive control: it must always pass, or the
problem is bigger than pod-to-pod.

```bash
kubectl run cn-client --image=busybox:1.36 --restart=Never --rm -i \
  --overrides='{"spec":{"nodeSelector":{"kubernetes.io/hostname":"high-palace"}}}' \
  --command -- sh -c \
  "nc -z -w 3 $SIP 8080 && echo CONNECT-OK || echo CONNECT-FAIL; \
   nc -z -w 3 10.43.0.10 53 && echo CLUSTERIP-OK || echo CLUSTERIP-FAIL"
```

Clean up:

```bash
kubectl delete pod cn-server --now
```

> `--rm -i` occasionally loses the attach output when the pod exits fast.
> If you get nothing, drop `--rm -i`, then `kubectl logs cn-client` and
> delete it manually.

## Interpreting results

| CONNECT | CLUSTERIP | Meaning |
|---|---|---|
| OK | OK | Pod network healthy. ADR-001's constraint no longer applies — consider superseding it. |
| FAIL | OK | **Expected state on this cluster.** kube-router is dropping pod-network forwards; ClusterIP DNAT path fine. Design per ADR-001. |
| FAIL | FAIL | Worse than baseline — kube-proxy/DNS also broken. Check `svclb`/kube-proxy pods and node iptables before anything else. |
| OK | FAIL | DNS/ClusterIP regression with working CNI. Suspect CoreDNS (see the [CoreDNS reboot runbook](coredns-fails-after-node-reboot.md)). |

## Captured baseline (2026-07-12)

Same-node probe, both pods on the control-plane node:

```
CONNECT-FAIL
CLUSTERIP-OK
```

Cross-node gives the identical result (full per-target diagnostic table in
the postmortem's root-cause section). If you ever see `CONNECT-OK`, update
ADR-001 before celebrating — something changed the CNI stack, and you want
to know what.
