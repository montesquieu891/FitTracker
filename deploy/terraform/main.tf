# FitTrack - OCI Infrastructure
# Terraform configuration for Oracle Cloud Infrastructure

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # OCI Object Storage compatible S3 backend
    bucket                      = "fittrack-terraform-state"
    key                         = "prod/terraform.tfstate"
    region                      = "us-ashburn-1"
    endpoint                    = "https://<namespace>.compat.objectstorage.us-ashburn-1.oraclecloud.com"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style            = true
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# --- Networking ---

resource "oci_core_vcn" "fittrack" {
  compartment_id = var.compartment_ocid
  display_name   = "fittrack-vcn"
  cidr_blocks    = ["10.0.0.0/16"]
  dns_label      = "fittrack"
}

resource "oci_core_subnet" "app" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.fittrack.id
  display_name      = "fittrack-app-subnet"
  cidr_block        = "10.0.1.0/24"
  dns_label         = "app"
  security_list_ids = [oci_core_security_list.app.id]
}

resource "oci_core_subnet" "db" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.fittrack.id
  display_name               = "fittrack-db-subnet"
  cidr_block                 = "10.0.2.0/24"
  dns_label                  = "db"
  prohibit_public_ip_on_vnic = true
  security_list_ids          = [oci_core_security_list.db.id]
}

resource "oci_core_internet_gateway" "fittrack" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fittrack.id
  display_name   = "fittrack-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fittrack.id
  display_name   = "fittrack-public-rt"

  route_rules {
    network_entity_id = oci_core_internet_gateway.fittrack.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

resource "oci_core_security_list" "app" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fittrack.id
  display_name   = "fittrack-app-sl"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
  }
}

resource "oci_core_security_list" "db" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.fittrack.id
  display_name   = "fittrack-db-sl"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6"
    source   = "10.0.1.0/24"
    tcp_options {
      min = 1521
      max = 1522
    }
  }
}

# --- Oracle Autonomous JSON Database ---

resource "oci_database_autonomous_database" "fittrack" {
  compartment_id           = var.compartment_ocid
  display_name             = "fittrack-${var.environment}"
  db_name                  = "fittrack"
  db_workload              = "AJD" # Autonomous JSON Database
  cpu_core_count           = var.db_cpu_core_count
  data_storage_size_in_tbs = var.db_storage_size_tb
  admin_password           = var.db_admin_password
  is_auto_scaling_enabled  = true
  is_free_tier             = var.environment == "dev"
  license_model            = "LICENSE_INCLUDED"
  subnet_id                = oci_core_subnet.db.id
  nsg_ids                  = []

  whitelisted_ips = []

  lifecycle {
    prevent_destroy = true
  }
}

# --- OCI Cache with Redis ---

resource "oci_redis_redis_cluster" "fittrack" {
  compartment_id     = var.compartment_ocid
  display_name       = "fittrack-cache-${var.environment}"
  node_count         = var.redis_node_count
  node_memory_in_gbs = var.redis_memory_gb
  software_version   = "REDIS_7_0"
  subnet_id          = oci_core_subnet.app.id
}

# --- Container Engine for Kubernetes (OKE) ---

resource "oci_containerengine_cluster" "fittrack" {
  compartment_id = var.compartment_ocid
  name           = "fittrack-${var.environment}"
  vcn_id         = oci_core_vcn.fittrack.id

  kubernetes_version = var.kubernetes_version

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = oci_core_subnet.app.id
  }

  options {
    service_lb_subnet_ids = [oci_core_subnet.app.id]
  }
}

resource "oci_containerengine_node_pool" "fittrack" {
  compartment_id     = var.compartment_ocid
  cluster_id         = oci_containerengine_cluster.fittrack.id
  name               = "fittrack-pool"
  kubernetes_version = var.kubernetes_version

  node_shape = var.node_shape
  node_shape_config {
    memory_in_gbs = var.node_memory_gb
    ocpus         = var.node_ocpus
  }

  node_config_details {
    size = var.node_pool_size
    placement_configs {
      availability_domain = var.availability_domain
      subnet_id           = oci_core_subnet.app.id
    }
  }

  node_source_details {
    image_id    = var.node_image_ocid
    source_type = "IMAGE"
  }
}

# --- Object Storage (for backups, assets) ---

resource "oci_objectstorage_bucket" "backups" {
  compartment_id = var.compartment_ocid
  name           = "fittrack-backups-${var.environment}"
  namespace      = var.object_storage_namespace

  versioning = "Enabled"

  lifecycle_rules {
    name        = "archive-old-backups"
    is_enabled  = true
    time_amount = 90
    time_unit   = "DAYS"
    target      = "objects"
    action      = "ARCHIVE"
  }
}

# --- OCI Queue (for async jobs) ---

resource "oci_queue_queue" "fittrack" {
  compartment_id              = var.compartment_ocid
  display_name                = "fittrack-jobs-${var.environment}"
  dead_letter_queue_delivery_count = 3
  retention_in_seconds        = 86400 # 24 hours
  visibility_in_seconds       = 300   # 5 minutes
}
