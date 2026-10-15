data "archive_file" "access" {
  type        = "zip"
  source_file = "${path.module}/functions/access.js"
  output_path = "${path.module}/access.zip"
}

resource "aws_cloudfront_public_key" "subscriber_cookie" {
  name        = "thedailysportspage-subscriber-cookie"
  comment     = "Public key for subscriber session cookies"
  encoded_key = file("${path.module}/keys/subscriber-cookie-public.pem")
}

resource "aws_cloudfront_key_group" "subscriber_cookie" {
  name    = "thedailysportspage-subscribers"
  comment = "Trusted key for verified subscriber sessions"
  items   = [aws_cloudfront_public_key.subscriber_cookie.id]
}

resource "aws_iam_role" "access" {
  name = "thedailysportspage-access-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "access" {
  name = "sign-subscriber-cookies-and-logs"
  role = aws_iam_role.access.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.google_play_credentials.arn,
          aws_secretsmanager_secret.subscriber_cookie_private_key.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.access.arn}:*"
      }
    ]
  })
}

resource "aws_secretsmanager_secret" "google_play_credentials" {
  name        = "thedailysportspage/google-play-service-account"
  description = "Google Play Android Publisher service account JSON; populate outside Terraform"
}

resource "aws_secretsmanager_secret" "subscriber_cookie_private_key" {
  name        = "thedailysportspage/subscriber-cookie-private-key"
  description = "Private key used only by the access Lambda to sign short-lived CloudFront cookies"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/lambda/thedailysportspage-access"
  retention_in_days = 30
}

resource "aws_lambda_function" "access" {
  function_name    = "thedailysportspage-access"
  role             = aws_iam_role.access.arn
  handler          = "access.handler"
  runtime          = "nodejs22.x"
  filename         = data.archive_file.access.output_path
  source_code_hash = data.archive_file.access.output_base64sha256
  timeout          = 5
  memory_size      = 128

  environment {
    variables = {
      APPLE_PRODUCT_ID          = var.apple_product_id
      APPLE_BUNDLE_ID           = var.apple_bundle_id
      APPLE_APP_ID              = var.apple_app_id
      APPLE_ROOT_SHA256         = join(",", var.apple_root_sha256)
      CLOUDFRONT_KEY_PAIR_ID    = aws_cloudfront_public_key.subscriber_cookie.id
      COOKIE_DOMAIN             = var.domain_name
      MAX_SESSION_SECONDS       = var.subscriber_session_seconds
      COOKIE_PRIVATE_KEY_SECRET = aws_secretsmanager_secret.subscriber_cookie_private_key.arn
      GOOGLE_CREDENTIALS_SECRET = aws_secretsmanager_secret.google_play_credentials.arn
      GOOGLE_PACKAGE_NAME       = var.google_package_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.access]
}

resource "aws_apigatewayv2_integration" "access" {
  api_id                 = aws_apigatewayv2_api.feedback.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.access.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "access" {
  api_id    = aws_apigatewayv2_api.feedback.id
  route_key = "POST /api/access/apple"
  target    = "integrations/${aws_apigatewayv2_integration.access.id}"
}

resource "aws_apigatewayv2_route" "access_google" {
  api_id    = aws_apigatewayv2_api.feedback.id
  route_key = "POST /api/access/google"
  target    = "integrations/${aws_apigatewayv2_integration.access.id}"
}

resource "aws_lambda_permission" "access" {
  statement_id  = "AllowAccessApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.access.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.feedback.execution_arn}/*/*"
}
