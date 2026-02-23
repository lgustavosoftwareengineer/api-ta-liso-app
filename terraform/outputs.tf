output "api_url" {
  description = "URL pública do API Gateway (URL original, sem domínio customizado)"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "acm_validation_cname_name" {
  description = "Registro CNAME para validar o certificado SSL — adicione no Namecheap (campo Host)"
  value       = tolist(aws_acm_certificate.api.domain_validation_options)[0].resource_record_name
}

output "acm_validation_cname_value" {
  description = "Valor do CNAME de validação SSL — adicione no Namecheap (campo Value)"
  value       = tolist(aws_acm_certificate.api.domain_validation_options)[0].resource_record_value
}

output "domain_cname_target" {
  description = "Aponte ta-liso-app.online para este endereço via ALIAS/CNAME no Namecheap"
  value       = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
}
