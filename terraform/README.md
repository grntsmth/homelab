# terraform/

OCI infrastructure definitions for the homelab. Provisions a VCN, internet gateway, route table, security list, public subnet, and two Always-Free ARM compute instances (`high-palace`, `star-garden`).

## Files

| File | Purpose |
|---|---|
| `provider.tf` | OCI provider + region pinning |
| `variables.tf` | Compartment OCID, region, CIDR blocks, image OCIDs, SSH public key |
| `data.tf` | Availability-domain lookups |
| `network.tf` | VCN, IGW, route table, security list, subnet |
| `compute.tf` | Two VM.Standard.A1.Flex instances |
| `outputs.tf` | Public/private IPs, OCIDs, hosted-service URLs |
| `import.sh` | Helper for importing existing resources into state |

## Using this

```bash
# Provide secrets (gitignored)
cp terraform.tfvars.example terraform.tfvars
# fill in tenancy_ocid, user_ocid, fingerprint, private_key_path, compartment_ocid, ssh_public_key

terraform init
terraform plan
terraform apply
```

## State is local

Right now `terraform.tfstate` lives on my workstation and is gitignored. That's fine for a single-operator homelab, but it's a known gap — if the workstation dies I'd have to `terraform import` every resource back.

**Planned:** migrate to an OCI Object Storage backend with state locking. Deferred only because the current scope is small enough that the risk is manageable and I'd rather land it properly (locking, encryption, versioning) than rush it.

## Security-list ingress

The `fortress_vcn` security list opens:

- `22/tcp` from `100.64.0.0/10` (Tailscale CGNAT only — no public SSH)
- `80/tcp`, `443/tcp` from `0.0.0.0/0` (Traefik + Let's Encrypt HTTP-01)
- ICMP type-3 for Path MTU Discovery

Everything else between nodes rides the Tailscale mesh, not the public internet.
