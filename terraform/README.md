# The Daily Sportz Page infrastructure

This stack owns the production infrastructure for `thedailysportspage.com`:

- private, encrypted, versioned S3 origin;
- CloudFront with Origin Access Control, HTTPS, security headers, and clean directory URLs;
- ACM certificate for the apex and `www` names;
- Route 53 hosted zone and alias records;
- GitHub Actions OIDC provider and a repository-scoped deployment role.

Resources are created in the SportzBallz AWS account through the `openclaw-agent`
profile. State is stored separately in the existing protected backend at
`s3://runmypool-terraform-state-739444271939/production/thedailysportspage.tfstate`
with native S3 lock files.

## Apply

```bash
terraform -chdir=terraform init
terraform -chdir=terraform plan -out=tfplan
terraform -chdir=terraform apply tfplan
```

The registered domain already delegates to the imported Route 53 hosted zone.
After the first apply, set the repository variables emitted by Terraform and enable
the GitHub Actions deployment. That workflow publishes the standalone copy to the
private S3 origin; the existing macOS LaunchAgent continues publishing the same
edition to `sportzballz.io/sportzpage/`.

The S3 bucket and CloudFront distribution use `prevent_destroy`. Removing the stack
therefore requires an explicit reviewed code change rather than an accidental destroy.
