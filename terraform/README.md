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

## Publication layout

The standalone domain publishes a public homepage at `/`, public sample editions
that are three through six days old under `/archive/`, and today’s complete edition
under `/subscriber/current/`. Subscriber content is designed to require a short-lived
CloudFront cookie issued only after the access Lambda validates a signed Apple
StoreKit transaction or a Google Play purchase token.

Subscriber enforcement is intentionally controlled by `enforce_subscriber_auth`.
Leave it `false` while deploying and testing compatible mobile builds, then set it
to `true` only after those builds are available to customers. When enabled, direct
browser requests to `/subscriber/*` fail closed without the signed cookies.

The cookie-signing private key and Google Play service-account JSON live in Secrets
Manager and must never be committed or placed in Terraform state. Their secret names
are `thedailysportspage/subscriber-cookie-private-key` and
`thedailysportspage/google-play-service-account`.

Each run also creates internal delivery artifacts under `/delivery/current/` for
a concise HTML digest, full HTML, print-ready HTML, and the public edition URL.
The separate macOS LaunchAgent continues to publish the SportzBallz edition.
