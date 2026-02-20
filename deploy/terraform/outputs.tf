# FitTrack - Terraform Outputs

output "vcn_id" {
  description = "VCN OCID"
  value       = oci_core_vcn.fittrack.id
}

output "app_subnet_id" {
  description = "Application subnet OCID"
  value       = oci_core_subnet.app.id
}

output "db_subnet_id" {
  description = "Database subnet OCID"
  value       = oci_core_subnet.db.id
}

output "autonomous_db_id" {
  description = "Autonomous JSON Database OCID"
  value       = oci_database_autonomous_database.fittrack.id
}

output "autonomous_db_connection_urls" {
  description = "Autonomous DB connection URLs"
  value       = oci_database_autonomous_database.fittrack.connection_urls
}

output "redis_cluster_id" {
  description = "OCI Cache (Redis) cluster OCID"
  value       = oci_redis_redis_cluster.fittrack.id
}

output "redis_primary_endpoint" {
  description = "Redis primary endpoint"
  value       = oci_redis_redis_cluster.fittrack.primary_endpoint_ip_address
}

output "oke_cluster_id" {
  description = "OKE cluster OCID"
  value       = oci_containerengine_cluster.fittrack.id
}

output "oke_cluster_endpoint" {
  description = "OKE cluster API endpoint"
  value       = oci_containerengine_cluster.fittrack.endpoints[0].public_endpoint
}

output "backup_bucket_name" {
  description = "Object Storage bucket for backups"
  value       = oci_objectstorage_bucket.backups.name
}

output "queue_id" {
  description = "OCI Queue OCID for async jobs"
  value       = oci_queue_queue.fittrack.id
}
