# --- OCI Authentication ---
variable "tenancy_ocid" {
  description = "OCID of the OCI tenancy"
  type        = string
}

variable "user_ocid" {
  description = "OCID of the OCI user for API authentication"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint of the OCI API signing key"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API private key PEM file"
  type        = string
  default     = "~/.oci/oci_api_key.pem"
}

variable "region" {
  description = "OCI region"
  type        = string
  default     = "us-ashburn-1"
}

# --- Compartment ---
variable "compartment_ocid" {
  description = "OCID of the compartment (defaults to root/tenancy)"
  type        = string
}

# --- Availability Domain ---
variable "availability_domain" {
  description = "Availability domain for compute and network resources"
  type        = string
}

# --- Network ---
variable "vcn_cidr" {
  description = "CIDR block for the VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.0.0/24"
}

# --- Compute ---
variable "instance_shape" {
  description = "OCI compute shape"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "Number of OCPUs for the flex instance (high-palace)"
  type        = number
  default     = 3
}

variable "instance_memory_in_gbs" {
  description = "Memory in GBs for the flex instance (high-palace)"
  type        = number
  default     = 18
}

variable "instance_image_ocid" {
  description = "OCID of the OS image (Oracle Linux 9 aarch64)"
  type        = string
}

variable "star_garden_ocpus" {
  description = "Number of OCPUs for star-garden (watchtower node)"
  type        = number
  default     = 1
}

variable "star_garden_memory_in_gbs" {
  description = "Memory in GBs for star-garden"
  type        = number
  default     = 6
}

variable "star_garden_boot_volume_size_in_gbs" {
  description = "Boot volume size in GBs for star-garden"
  type        = number
  default     = 100
}

variable "star_garden_ssh_public_key" {
  description = "SSH public key authorized on star-garden"
  type        = string
}

variable "boot_volume_size_in_gbs" {
  description = "Boot volume size in GBs for high-palace"
  type        = number
  default     = 47
}

variable "ssh_public_key" {
  description = "SSH public key authorized on high-palace"
  type        = string
}
