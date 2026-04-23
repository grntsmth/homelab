output "instance_ocid" {
  description = "OCID of the high-palace compute instance"
  value       = oci_core_instance.high_palace.id
}

output "instance_public_ip" {
  description = "Public IP of high-palace"
  value       = oci_core_instance.high_palace.public_ip
}

output "instance_private_ip" {
  description = "Private IP of high-palace"
  value       = oci_core_instance.high_palace.private_ip
}

output "star_garden_ocid" {
  description = "OCID of the star-garden compute instance"
  value       = oci_core_instance.star_garden.id
}

output "star_garden_public_ip" {
  description = "Public IP of star-garden"
  value       = oci_core_instance.star_garden.public_ip
}

output "star_garden_private_ip" {
  description = "Private IP of star-garden"
  value       = oci_core_instance.star_garden.private_ip
}

output "vcn_ocid" {
  description = "OCID of the homelab VCN"
  value       = oci_core_vcn.fortress_vcn.id
}

output "subnet_ocid" {
  description = "OCID of the homelab public subnet"
  value       = oci_core_subnet.fortress_subnet.id
}
