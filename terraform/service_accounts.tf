# -----------------------------------------------------------------------------
# dbt service account - BigQuery only
# -----------------------------------------------------------------------------
resource "google_service_account" "dbt_bigquery" {
  account_id   = "dbt-bigquery"
  display_name = "dbt BigQuery"
  project      = var.project_id
}

resource "google_project_iam_member" "dbt_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dbt_bigquery.email}"
}

resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt_bigquery.email}"
}

# -----------------------------------------------------------------------------
# Orchestrator service account - GCS + BigQuery
# -----------------------------------------------------------------------------
resource "google_service_account" "orchestrator" {
  account_id   = "orchestrator"
  display_name = "Orchestrator"
  project      = var.project_id
}

# GCS: access to the single data bucket
resource "google_storage_bucket_iam_member" "orchestrator_bucket" {
  bucket = google_storage_bucket.gaming-data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.orchestrator.email}"
}

# BigQuery: run jobs and edit data
resource "google_project_iam_member" "orchestrator_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}
