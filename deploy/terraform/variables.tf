# FitTrack - Terraform Variables

# --- OCI Provider ---

variable "tenancy_ocid" {
  description = "OCI tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI user OCID for API authentication"
  type        = string
}

variable "fingerprint" {
  description = "API key fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to OCI API private key file"
  type        = string
}

variable "region" {
  description = "OCI region (e.g., us-ashburn-1)"
  type        = string
  default     = "us-ashburn-1"
}

variable "compartment_ocid" {
  description = "OCI compartment OCID for all resources"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "availability_domain" {
  description = "OCI availability domain for compute placement"
  type        = string
}

# --- Database ---

variable "db_cpu_core_count" {
  description = "Autonomous DB OCPU count"
  type        = number
  default     = 1
}

variable "db_storage_size_tb" {
  description = "Autonomous DB storage in TB"
  type        = number
  default     = 1
}

variable "db_admin_password" {
  description = "Admin password for Autonomous DB"
  type        = string
  sensitive   = true
}

# --- Redis / OCI Cache ---

variable "redis_node_count" {
  description = "Number of Redis cluster nodes"
  type        = number
  default     = 3
}

variable "redis_memory_gb" {
  description = "Memory per Redis node in GB"
  type        = number
  default     = 2
}

# --- Kubernetes / OKE ---

variable "kubernetes_version" {
  description = "Kubernetes version for OKE cluster"
  type        = string
  default     = "v1.30.1"
}

variable "node_shape" {
  description = "OCI compute shape for worker nodes"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "node_ocpus" {
  description = "OCPUs per worker node"
  type        = number
  default     = 2
}

variable "node_memory_gb" {
  description = "Memory per worker node in GB"
  type        = number
  default     = 16
}

variable "node_pool_size" {
  description = "Number of worker nodes"
  type        = number
  default     = 3
}

variable "node_image_ocid" {
  description = "OKE worker node image OCID (Oracle Linux)"
  type        = string
}

# --- Object Storage ---

variable "object_storage_namespace" {
  description = "OCI Object Storage namespace"
  type        = string
}
