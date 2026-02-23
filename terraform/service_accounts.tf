# -----------------------------------------------------------------------------
# dbt service account - BigQuery only
# -----------------------------------------------------------------------------
resource "google_service_account" "dbt_bigquery" {
  account_id   = "dbt-bigquery"
  display_name = "dbt BigQuery"
  project      = var.project_id

  depends_on = [google_project_service.iam]
}

resource "google_project_iam_member" "dbt_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dbt_bigquery.email}"

  depends_on = [google_project_service.resource_manager]
}

resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt_bigquery.email}"

  depends_on = [google_project_service.resource_manager]
}

# -----------------------------------------------------------------------------
# Orchestrator service account - GCS + BigQuery
# -----------------------------------------------------------------------------
resource "google_service_account" "orchestrator" {
  account_id   = "orchestrator"
  display_name = "Orchestrator"
  project      = var.project_id

  depends_on = [google_project_service.iam]
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

  depends_on = [google_project_service.resource_manager]
}

resource "google_project_iam_member" "orchestrator_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"

  depends_on = [google_project_service.resource_manager]
}
