resource "aws_lambda_function" "api" {
  function_name = "ta-liso-api"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      AWS_SECRETS_NAME             = var.secrets_name
      PORT                         = "8000"
      AWS_LAMBDA_EXEC_WRAPPER      = "/opt/extensions/lambda-adapter"
      READINESS_CHECK_PATH         = "/health"
    }
  }
}

resource "aws_lambda_function" "migrations" {
  function_name = "ta-liso-migrations"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  timeout       = 300

  image_config {
    command = ["migrations_handler.handler"]
  }

  environment {
    variables = {
      AWS_SECRETS_NAME = var.secrets_name
    }
  }
}
