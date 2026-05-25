# Runbooks

Procedural docs for triaging and resolving known failure modes in this homelab. The audience is me (single-operator), but the format is written for a future on-call who has never seen the system before.

## When to write a new runbook

After the *second* time I've had to chase down the same symptom from scratch. Once is a fluke; twice means future-me deserves a checklist. Runbooks are not a place for theoretical failure modes — only ones that have actually happened here.

## Format

Each runbook is a single Markdown file named `<kebab-case-symptom>.md`. Suggested structure:

```markdown
# <Symptom in 5–8 words>

**Severity:** {warning | critical}
**Pages:** {Discord channel / human on call}
**First seen:** YYYY-MM-DD
**Related alerts:** `AlertName` (`monitoring/monitoring.yml`)

## Symptoms

What the operator notices first: the alert text, the Discord message,
the dashboard reading, the user report.

## Likely causes

Ordered by historical frequency. Don't enumerate every theoretical cause —
list the ones that have actually triggered this symptom here.

## Diagnostic steps

Commands to run in order. Copy-pasteable. Include the expected output
and what it means.

```bash
kubectl -n monitoring get pods -o wide
```

## Mitigation

Smallest action that restores service. Distinguish from root-cause fix.

## Root-cause fix

The actual repair. Link to the PR that landed it if applicable.

## Prevention

What monitoring/alerting/automation would have prevented this, or caught
it earlier. Track as a TODO if not yet implemented.
```

## Index

| Runbook | Severity | Symptom |
|---|---|---|
| [coredns-fails-after-node-reboot.md](coredns-fails-after-node-reboot.md) | critical | Pods can't resolve DNS after a node returns from reboot; CoreDNS upstream pointed at unreachable Tailscale MagicDNS. |
