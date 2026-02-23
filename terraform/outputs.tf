output "bucket_name" {
  description = "Name of the GCS data bucket"
  value       = google_storage_bucket.gaming-data.name
}

output "bigquery_dataset_bronze" {
  description = "BigQuery bronze dataset ID"
  value       = google_bigquery_dataset.bronze.dataset_id
}

output "bigquery_dataset_silver" {
  description = "BigQuery silver dataset ID"
  value       = google_bigquery_dataset.silver.dataset_id
}

output "bigquery_dataset_gold" {
  description = "BigQuery gold dataset ID"
  value       = google_bigquery_dataset.gold.dataset_id
}

output "dbt_sa_email" {
  description = "Service account email for dbt (BigQuery)"
  value       = google_service_account.dbt_bigquery.email
}

output "orchestrator_sa_email" {
  description = "Service account email for the orchestrator"
  value       = google_service_account.orchestrator.email
}
