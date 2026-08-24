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
