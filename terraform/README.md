# The Daily Sportz Page infrastructure

This stack owns the production infrastructure for `thedailysportspage.com`:

- private, encrypted, versioned S3 origin;
- CloudFront with Origin Access Control, HTTPS, security headers, and clean directory URLs;
- ACM certificate for the apex and `www` names;
- Route 53 hosted zone and alias records;
- GitHub Actions OIDC provider and a repository-scoped deployment role.
- CloudFront standard access logs (v2) in JSON in a private, encrypted S3 bucket
  and retained for 90 days by default.

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

For browser-level page views and referrers, create a Cloudflare Web Analytics site
for `thedailysportspage.com` and set its public token as the GitHub Actions variable
`CLOUDFLARE_WEB_ANALYTICS_TOKEN`. The generated baseball and football pages include
the beacon only when that variable is populated.

## Subscription-ready publication layout

The standalone domain publishes a public teaser at `/`, a rolling seven-edition
free archive under `/archive/`, and today’s complete edition under
`/subscriber/current/`. The subscriber and delivery prefixes are temporarily public
for output monitoring. Restore the CloudFront gate when Stripe-backed authentication
is connected.

Each run also creates protected delivery artifacts under `/delivery/current/` for
a concise HTML digest, full HTML, print-ready HTML, and the protected web URL.
The separate macOS LaunchAgent continues to publish the free SportzBallz edition.
