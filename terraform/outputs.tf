output "bucket_name" {
  description = "Private S3 origin bucket used by the deployment workflow."
  value       = aws_s3_bucket.site.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution invalidated after each deployment."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  description = "CloudFront hostname available before registrar delegation completes."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "github_deploy_role_arn" {
  description = "OIDC role assumed by the SportzPage GitHub Actions workflow."
  value       = aws_iam_role.github_deploy.arn
}

output "route53_name_servers" {
  description = "Set these nameservers at the domain registrar."
  value       = aws_route53_zone.site.name_servers
}

output "site_urls" {
  value = {
    baseball = "https://${var.domain_name}/"
    football = "https://${var.domain_name}/football/"
  }
}
