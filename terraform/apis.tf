# Enable GCP APIs required for GCS and BigQuery.
# Terraform will enable these before creating resources that depend on them.

resource "google_project_service" "storage" {
  project = var.project_id
  service = "storage.googleapis.com"
}

resource "google_project_service" "bigquery" {
  project = var.project_id
  service = "bigquery.googleapis.com"
}

resource "google_project_service" "bigquery_storage" {
  project = var.project_id
  service = "bigquerystorage.googleapis.com"
}

resource "google_project_service" "iam" {
  project = var.project_id
  service = "iam.googleapis.com"
}

resource "google_project_service" "resource_manager" {
  project = var.project_id
  service = "cloudresourcemanager.googleapis.com"
}
