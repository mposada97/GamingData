variable "project_id" {
  type        = string
  description = "This is the project id"
  default     = "gamingdata-487900"
}
variable "region" {
  type        = string
  description = "A description of the variable's purpose"
  default     = "US"
}
variable "bucket_name" {
  type        = string
  description = "Bucket to land RAWG API Gaming Data"
  default     = "gamingdata-487900-bucket"
}

