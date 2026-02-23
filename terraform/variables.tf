variable "aws_region" {
  description = "Região AWS"
  default     = "us-east-1"
}

variable "image_uri" {
  description = "URI da imagem ECR com tag (ex: 316777090101.dkr.ecr.us-east-1.amazonaws.com/ta-liso-api:sha-abc123)"
}

variable "secrets_name" {
  description = "Nome do secret no AWS Secrets Manager"
  default     = "talisoapp/develop"
}
