#!/bin/bash
# Import existing OCI resources into Terraform state.
#
# Usage:
#   1. Fill in the OCIDs below from the OCI Console
#      (Networking > Virtual Cloud Networks > click your VCN)
#   2. Run: terraform init
#   3. Run: bash import.sh
#   4. Run: terraform plan  (should show 0 changes if config matches)
#
# The instance OCID is already known from metadata.
# Network OCIDs must be looked up in OCI Console or via OCI CLI:
#   oci network vcn list --compartment-id <COMPARTMENT_OCID>
#   oci network subnet list --compartment-id <COMPARTMENT_OCID>
#   oci network internet-gateway list --compartment-id <COMPARTMENT_OCID> --vcn-id <VCN_OCID>
#   oci network route-table list --compartment-id <COMPARTMENT_OCID> --vcn-id <VCN_OCID>
#   oci network security-list list --compartment-id <COMPARTMENT_OCID> --vcn-id <VCN_OCID>

set -euo pipefail

# --- Fill these in from OCI Console ---
VCN_OCID="ocid1.vcn.oc1.<region>.<REDACTED>"
SUBNET_OCID="ocid1.subnet.oc1.<region>.<REDACTED>"
IGW_OCID="ocid1.internetgateway.oc1.<region>.<REDACTED>"
RT_OCID="ocid1.routetable.oc1.<region>.<REDACTED>"
SL_OCID="ocid1.securitylist.oc1.<region>.<REDACTED>"

# Instance OCIDs
HIGH_PALACE_OCID="ocid1.instance.oc1.<region>.<REDACTED>"
STAR_GARDEN_OCID="ocid1.instance.oc1.<region>.<REDACTED>"

echo "Importing OCI resources into Terraform state..."

terraform import oci_core_vcn.fortress_vcn "$VCN_OCID"
terraform import oci_core_internet_gateway.fortress_igw "$IGW_OCID"
terraform import oci_core_route_table.fortress_rt "$RT_OCID"
terraform import oci_core_security_list.fortress_sl "$SL_OCID"
terraform import oci_core_subnet.fortress_subnet "$SUBNET_OCID"
terraform import oci_core_instance.high_palace "$HIGH_PALACE_OCID"
terraform import oci_core_instance.star_garden "$STAR_GARDEN_OCID"

echo ""
echo "Import complete. Run 'terraform plan' to verify state matches config."
