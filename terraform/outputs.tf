output "api_url" {
  description = "URL pública do API Gateway"
  value       = aws_apigatewayv2_stage.default.invoke_url
}
