variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for the ElastiCache subnet group"
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = <<-EOT
    Security groups permitted to reach Redis on 6379. Typically the
    API task SG + worker task SG (worker doesn't authenticate today,
    but beat-scheduled tasks that do may appear any time — include it
    defensively).
  EOT
}

variable "node_type" {
  type        = string
  default     = "cache.t4g.micro"
  description = "ElastiCache node type. Default cache.t4g.micro ≈ $1/mo."
}
