data "aws_caller_identity" "current" {}

locals {
  bucket_name             = "thedailysportspage-com-${data.aws_caller_identity.current.account_id}"
  access_logs_bucket_name = "${local.bucket_name}-access-logs"
  tags = {
    Application = "The Daily Sportz Page"
    Environment = "production"
    ManagedBy   = "Terraform"
    Repository  = var.github_repository
  }
}

resource "aws_s3_bucket" "access_logs" {
  bucket        = local.access_logs_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.access_log_retention_days
    }
  }
}

resource "aws_route53_zone" "site" {
  name    = var.domain_name
  comment = "Managed by Terraform for The Daily Sportz Page"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_acm_certificate" "site" {
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "certificate_validation" {
  for_each = toset([var.domain_name, "www.${var.domain_name}"])

  allow_overwrite = true
  zone_id         = aws_route53_zone.site.zone_id
  name = one([
    for option in aws_acm_certificate.site.domain_validation_options :
    option.resource_record_name if option.domain_name == each.value
  ])
  type = one([
    for option in aws_acm_certificate.site.domain_validation_options :
    option.resource_record_type if option.domain_name == each.value
  ])
  ttl = 300
  records = [one([
    for option in aws_acm_certificate.site.domain_validation_options :
    option.resource_record_value if option.domain_name == each.value
  ])]
}

resource "aws_acm_certificate_validation" "site" {
  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for record in aws_route53_record.certificate_validation : record.fqdn]
}

resource "aws_s3_bucket" "site" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "thedailysportspage-s3-oac"
  description                       = "Private S3 access for The Daily Sportz Page"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "directory_index" {
  name    = "thedailysportspage-directory-index"
  runtime = "cloudfront-js-2.0"
  comment = "Resolve clean directory URLs to index.html"
  publish = true
  code    = file("${path.module}/functions/directory-index.js")
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name    = "thedailysportspage-security-headers"
  comment = "Security headers for The Daily Sportz Page"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "SAMEORIGIN"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "The Daily Sportz Page"
  default_root_object = "index.html"
  aliases             = [var.domain_name, "www.${var.domain_name}"]
  price_class         = "PriceClass_100"
  http_version        = "http2and3"
  wait_for_deployment = true

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "private-s3-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id           = "private-s3-origin"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD", "OPTIONS"]
    compress                   = true
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.directory_index.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.site.certificate_arn
    minimum_protocol_version = "TLSv1.2_2021"
    ssl_support_method       = "sni-only"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cloudwatch_log_delivery_source" "cloudfront_access" {
  name         = "thedailysportspage-cloudfront-access"
  resource_arn = aws_cloudfront_distribution.site.arn
  log_type     = "ACCESS_LOGS"
}

resource "aws_cloudwatch_log_delivery_destination" "cloudfront_access" {
  name          = "thedailysportspage-cloudfront-access-s3"
  output_format = "json"

  delivery_destination_configuration {
    destination_resource_arn = aws_s3_bucket.access_logs.arn
  }

  depends_on = [
    aws_s3_bucket_ownership_controls.access_logs,
    aws_s3_bucket_public_access_block.access_logs,
    aws_s3_bucket_server_side_encryption_configuration.access_logs,
  ]
}

resource "aws_cloudwatch_log_delivery" "cloudfront_access" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.cloudfront_access.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.cloudfront_access.arn
}

data "aws_iam_policy_document" "origin" {
  statement {
    sid       = "AllowCloudFrontReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "origin" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.origin.json
}

resource "aws_route53_record" "apex_a" {
  zone_id = aws_route53_zone.site.zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "apex_aaaa" {
  zone_id = aws_route53_zone.site.zone_id
  name    = var.domain_name
  type    = "AAAA"
  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "www_a" {
  zone_id = aws_route53_zone.site.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "www_aaaa" {
  zone_id = aws_route53_zone.site.zone_id
  name    = "www.${var.domain_name}"
  type    = "AAAA"
  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}
