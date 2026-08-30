data "archive_file" "feedback" {
  type        = "zip"
  source_file = "${path.module}/functions/feedback.py"
  output_path = "${path.module}/feedback.zip"
}

resource "aws_dynamodb_table" "feedback" {
  name         = "thedailysportspage-feedback"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_sesv2_email_identity" "feedback" {
  email_identity = "agsmith11@gmail.com"
}

resource "aws_iam_role" "feedback" {
  name = "thedailysportspage-feedback-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "feedback" {
  name = "feedback-write-and-logs"
  role = aws_iam_role.feedback.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.feedback.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.feedback.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = aws_sesv2_email_identity.feedback.arn
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "feedback" {
  name              = "/aws/lambda/thedailysportspage-feedback"
  retention_in_days = 30
}

resource "aws_lambda_function" "feedback" {
  function_name    = "thedailysportspage-feedback"
  role             = aws_iam_role.feedback.arn
  handler          = "feedback.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.feedback.output_path
  source_code_hash = data.archive_file.feedback.output_base64sha256
  timeout          = 5
  memory_size      = 128

  environment {
    variables = {
      FEEDBACK_TABLE = aws_dynamodb_table.feedback.name
      FEEDBACK_EMAIL = aws_sesv2_email_identity.feedback.email_identity
    }
  }

  depends_on = [aws_cloudwatch_log_group.feedback]
}

resource "aws_apigatewayv2_api" "feedback" {
  name          = "thedailysportspage-feedback"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "feedback" {
  api_id                 = aws_apigatewayv2_api.feedback.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.feedback.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "feedback" {
  api_id    = aws_apigatewayv2_api.feedback.id
  route_key = "POST /api/feedback"
  target    = "integrations/${aws_apigatewayv2_integration.feedback.id}"
}

resource "aws_apigatewayv2_stage" "feedback" {
  api_id      = aws_apigatewayv2_api.feedback.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 5
    throttling_rate_limit  = 2
  }
}

resource "aws_lambda_permission" "feedback" {
  statement_id  = "AllowFeedbackApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.feedback.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.feedback.execution_arn}/*/*"
}
