output "redis_primary_endpoint" {
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
  description = "Primary endpoint hostname for Redis."
}

output "redis_port" {
  value       = 6379
  description = "Redis port."
}

output "redis_url_ssm_parameter_name" {
  value       = aws_ssm_parameter.redis_url.name
  description = "SSM parameter name holding the REDIS_URL SecureString."
}

output "redis_url_ssm_parameter_arn" {
  value       = aws_ssm_parameter.redis_url.arn
  description = "SSM parameter ARN, wired into ECS task secrets."
}

output "cache_security_group_id" {
  value       = aws_security_group.cache.id
  description = "Security group protecting the ElastiCache cluster."
}
