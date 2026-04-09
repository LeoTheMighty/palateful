# RDS PostgreSQL instance

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
  description = "Subnet IDs for DB subnet group"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for the DB instance"
}

variable "instance_class" {
  type        = string
  default     = "db.t4g.micro"
  description = "RDS instance class"
}

variable "allocated_storage" {
  type        = number
  default     = 20
  description = "Allocated storage in GB"
}

variable "db_name" {
  type        = string
  default     = "palateful"
  description = "Database name"
}

variable "db_username" {
  type        = string
  default     = "palateful"
  description = "Master database username"
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-${var.environment}"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.project}-db-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.project}-db-${var.environment}"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username

  # AWS manages the master password in Secrets Manager automatically
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = var.security_group_ids

  publicly_accessible = false
  multi_az            = false

  backup_retention_period   = 7
  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project}-db-final-${var.environment}" : null

  apply_immediately = true

  tags = {
    Name        = "${var.project}-db-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# Outputs

output "db_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "RDS endpoint (host:port)"
}

output "db_address" {
  value       = aws_db_instance.main.address
  description = "RDS hostname"
}

output "db_port" {
  value       = aws_db_instance.main.port
  description = "RDS port"
}

output "db_name" {
  value = aws_db_instance.main.db_name
}

output "db_username" {
  value = aws_db_instance.main.username
}

output "db_master_secret_arn" {
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
  description = "ARN of the AWS-managed master password secret"
}

output "db_instance_id" {
  value = aws_db_instance.main.id
}
