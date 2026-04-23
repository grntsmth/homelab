# --- VCN ---
resource "oci_core_vcn" "fortress_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "vcn-20260219-1839"
  dns_label      = "vcn02191841"
}

# --- Internet Gateway ---
resource "oci_core_internet_gateway" "fortress_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fortress_vcn.id
  display_name   = "Internet Gateway vcn-20260219-1839"
  enabled        = true
}

# --- Route Table ---
resource "oci_core_route_table" "fortress_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fortress_vcn.id
  display_name   = "Default Route Table for vcn-20260219-1839"

  route_rules {
    network_entity_id = oci_core_internet_gateway.fortress_igw.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

# --- Security List ---
resource "oci_core_security_list" "fortress_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fortress_vcn.id
  display_name   = "Default Security List for vcn-20260219-1839"

  # Allow all egress
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  # SSH — Tailscale mesh only (100.64.0.0/10 CGNAT range)
  ingress_security_rules {
    description = "SSH via Tailscale only"
    source      = "100.64.0.0/10"
    protocol    = "6" # TCP
    stateless   = false
    tcp_options {
      min = 22
      max = 22
    }
  }

  # HTTP (Traefik)
  ingress_security_rules {
    description = "Allow HTTP Connections"
    source      = "0.0.0.0/0"
    protocol    = "6"
    stateless   = false
    tcp_options {
      min = 80
      max = 80
    }
  }

  # HTTPS (Traefik + Let's Encrypt TLS)
  ingress_security_rules {
    description = "Allow Https"
    source      = "0.0.0.0/0"
    protocol    = "6"
    stateless   = false
    tcp_options {
      min = 443
      max = 443
    }
  }

  # ICMP - Path MTU Discovery (from internet)
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "1" # ICMP
    stateless = false
    icmp_options {
      type = 3
      code = 4
    }
  }

  # ICMP - All type 3 from VCN
  ingress_security_rules {
    source    = "10.0.0.0/16"
    protocol  = "1"
    stateless = false
    icmp_options {
      type = 3
      code = -1
    }
  }
}

# --- Public Subnet ---
resource "oci_core_subnet" "fortress_subnet" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.fortress_vcn.id
  cidr_block                 = var.subnet_cidr
  display_name               = "subnet-20260219-1839"
  dns_label                  = "subnet02191841"
  route_table_id             = oci_core_route_table.fortress_rt.id
  security_list_ids          = [oci_core_security_list.fortress_sl.id]
  prohibit_public_ip_on_vnic = false
}
