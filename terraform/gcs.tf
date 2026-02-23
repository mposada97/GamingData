resource "google_storage_bucket" "gaming-data" {
  name                     = var.bucket_name
  location                 = var.region
  force_destroy            = true
  storage_class            = "STANDARD"
  public_access_prevention = "enforced"

  depends_on = [google_project_service.storage]

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
}