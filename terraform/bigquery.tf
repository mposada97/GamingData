# -----------------------------------------------------------------------------
# Bronze: raw landing; external tables over GCS bucket (Parquet)
# -----------------------------------------------------------------------------
# Dataset access: WRITER includes read and write. dbt and orchestrator need both.
# Project owner already have access via project IAM; no need to list here.
resource "google_bigquery_dataset" "bronze" {
  dataset_id    = "bronze"
  project       = var.project_id
  location      = var.region
  friendly_name = "bronze"
  description   = "Raw data layer; external tables over GCS landing."

  depends_on = [google_project_service.bigquery, google_project_service.bigquery_storage]

  access {
    role          = "WRITER"
    user_by_email = google_service_account.dbt_bigquery.email
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.orchestrator.email
  }
}

# External table: reads Parquet from gs://<bucket>/raw/
# Duplicate this resource (and change table_id + source_uris) for other entities.
resource "google_bigquery_table" "bronze_external_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id   = "raw_external"
  project    = var.project_id

  depends_on = [google_project_service.bigquery, google_project_service.bigquery_storage]

  external_data_configuration {
    autodetect    = true
    source_format = "PARQUET"
    source_uris   = ["gs://${var.bucket_name}/raw/*"]
  }
}

# -----------------------------------------------------------------------------
# Silver / Gold: refined and mart layers (WRITER = read + write for dbt/orchestrator)
# -----------------------------------------------------------------------------
resource "google_bigquery_dataset" "silver" {
  dataset_id    = "silver"
  project       = var.project_id
  location      = var.region
  friendly_name = "silver"
  description   = "Cleaned and conformed layer."

  depends_on = [google_project_service.bigquery, google_project_service.bigquery_storage]

  access {
    role          = "WRITER"
    user_by_email = google_service_account.dbt_bigquery.email
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.orchestrator.email
  }
}

resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  project       = var.project_id
  location      = var.region
  friendly_name = "gold"
  description   = "Business-level aggregates and marts."

  depends_on = [google_project_service.bigquery, google_project_service.bigquery_storage]

  access {
    role          = "WRITER"
    user_by_email = google_service_account.dbt_bigquery.email
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.orchestrator.email
  }
}
