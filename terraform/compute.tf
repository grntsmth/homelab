resource "oci_core_instance" "high_palace" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "High-Palace"
  fault_domain        = "FAULT-DOMAIN-1"
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = var.instance_image_ocid
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.fortress_subnet.id
    private_ip       = "10.0.0.x"
    assign_public_ip = true
    hostname_label   = "high-palace"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
  }

  agent_config {
    is_management_disabled = false
    is_monitoring_disabled = false

    plugins_config {
      name          = "WebLogic Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Vulnerability Scanning"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Oracle Java Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "OS Management Hub Agent"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Management Agent"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Fleet Application Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Custom Logs Monitoring"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute RDMA GPU Monitoring"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Compute Instance Run Command"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute Instance Monitoring"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute HPC RDMA Auto-Configuration"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Compute HPC RDMA Authentication"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Cloud Guard Workload Protection"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Block Volume Management"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Bastion"
      desired_state = "DISABLED"
    }
  }

  # Prevent recreation when the image is updated upstream
  lifecycle {
    ignore_changes = [source_details[0].source_id]
  }
}

resource "oci_core_instance" "star_garden" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "Star-Garden"
  fault_domain        = "FAULT-DOMAIN-1"
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.star_garden_ocpus
    memory_in_gbs = var.star_garden_memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = var.instance_image_ocid
    boot_volume_size_in_gbs = var.star_garden_boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.fortress_subnet.id
    assign_public_ip = true
    hostname_label   = "star-garden"
  }

  metadata = {
    ssh_authorized_keys = var.star_garden_ssh_public_key
  }

  agent_config {
    is_management_disabled = false
    is_monitoring_disabled = false

    plugins_config {
      name          = "WebLogic Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Vulnerability Scanning"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Oracle Java Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "OS Management Hub Agent"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Management Agent"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Fleet Application Management Service"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Custom Logs Monitoring"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute RDMA GPU Monitoring"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Compute Instance Run Command"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute Instance Monitoring"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Compute HPC RDMA Auto-Configuration"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Compute HPC RDMA Authentication"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Cloud Guard Workload Protection"
      desired_state = "ENABLED"
    }
    plugins_config {
      name          = "Block Volume Management"
      desired_state = "DISABLED"
    }
    plugins_config {
      name          = "Bastion"
      desired_state = "DISABLED"
    }
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id]
  }
}
