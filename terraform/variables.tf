variable "aws_region" {
  description = "AWS region for the S3 origin and global-service API calls."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile for the SportzBallz account that owns the domain."
  type        = string
  default     = "openclaw-agent"
}

variable "domain_name" {
  description = "Canonical domain for The Daily Sportz Page."
  type        = string
  default     = "thedailysportspage.com"
}

variable "github_repository" {
  description = "GitHub repository allowed to deploy through OIDC."
  type        = string
  default     = "sportzballz/sportzpage"
}

variable "force_destroy_bucket" {
  description = "Allow Terraform to delete a non-empty origin bucket. Keep false in production."
  type        = bool
  default     = false
}

variable "access_log_retention_days" {
  description = "Number of days to retain CloudFront access logs in S3."
  type        = number
  default     = 90

  validation {
    condition     = var.access_log_retention_days >= 30
    error_message = "Access logs must be retained for at least 30 days."
  }
}

variable "enforce_subscriber_auth" {
  description = "Require a server-verified signed cookie on /subscriber/*. Enable only after the compatible mobile build is available."
  type        = bool
  default     = false
}

variable "subscriber_session_seconds" {
  description = "Maximum lifetime of a subscriber web session."
  type        = number
  default     = 86400
}

variable "apple_bundle_id" {
  type    = string
  default = "com.thedailysportspage.app"
}

variable "apple_product_id" {
  type    = string
  default = "com.thedailysportspage.app.monthly"
}

variable "apple_app_id" {
  type    = string
  default = "6808274175"
}

variable "apple_root_sha256" {
  description = "SHA-256 fingerprints of Apple roots trusted for StoreKit transaction JWS validation."
  type        = list(string)
  default = [
    "B0B1730ECBC7FF4505142C49F1295E6EDA6BCAED7E2C68C5BE91B5A11001F024",
    "C2B9B042DD57830E7D117DAC55AC8AE19407D38E41D88F3215BC3A890444A050",
    "63343ABFB89A6A03EBB57E9B3F5FA7BE7C4F5C756F3017B3A8C488C3653E9179",
  ]
}

variable "google_package_name" {
  type    = string
  default = "com.thedailysportspage.app"
}
