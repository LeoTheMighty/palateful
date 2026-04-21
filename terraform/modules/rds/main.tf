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

# ─── pim-2 (2026-04-21) — perf-tuning knobs ───

variable "maintenance_window" {
  type        = string
  default     = "tue:07:00-tue:08:00"
  description = <<-EOT
    Preferred maintenance window in UTC.
    Default tue:07:00-tue:08:00 UTC = midnight Pacific, low-risk for the
    current single-user prod. Static parameter-group values
    (shared_buffers, max_connections) land at this window. Change via
    terraform, not the AWS console, so the state stays canonical.
  EOT
}

variable "performance_insights_enabled" {
  type        = bool
  default     = true
  description = <<-EOT
    Enable Performance Insights. Free for 6 months on t4g.small, then
    ~$2/mo. Turn off if cost ceiling becomes a concern; calendar
    reminder in BUGS.md at day 170 to decide.
  EOT
}

variable "performance_insights_retention_period" {
  type        = number
  default     = 7
  description = "Performance Insights retention in days. 7 stays on free tier."
}

variable "enabled_cloudwatch_logs_exports" {
  type        = list(string)
  default     = ["postgresql"]
  description = <<-EOT
    Postgres logs to stream to CloudWatch. `postgresql` = combined
    error/slow-query log; `upgrade` is separate. log_min_duration_statement
    (set in the parameter group) controls which queries hit this log.
  EOT
}

variable "apply_immediately" {
  type        = bool
  default     = false
  description = <<-EOT
    Whether to apply RDS instance modifications immediately. `false`
    defers pending-reboot changes to the maintenance_window so a
    terraform apply cannot trigger a surprise reboot. Dynamic
    parameter-group values still apply immediately because the
    parameter group sets `apply_method = immediate` on those.
  EOT
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

  # pim-2 (2026-04-21): attach the perf-tuned parameter group. Dynamic
  # values (work_mem, maintenance_work_mem, effective_cache_size,
  # log_min_duration_statement) hot-apply; static values (shared_buffers,
  # max_connections) land at the next maintenance-window reboot via
  # pending-reboot.
  parameter_group_name = aws_db_parameter_group.perf.name

  publicly_accessible = false
  multi_az            = false

  backup_retention_period   = 7
  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project}-db-final-${var.environment}" : null

  # pim-2 (2026-04-21): schedule static-param reboots for a predictable
  # window instead of letting AWS pick. Midnight Pacific = low-risk for
  # single-user prod. Affects both engine-minor upgrades and the
  # pending-reboot application of static parameter-group values.
  maintenance_window = var.maintenance_window

  # pim-2 (2026-04-21): opt into Performance Insights (free tier on
  # t4g.small for 6 months, ~$2/mo after) + ship postgresql slow-query
  # log to CloudWatch. log_min_duration_statement = 100 (set in the
  # parameter group) controls which queries hit the log.
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_retention_period
  enabled_cloudwatch_logs_exports       = var.enabled_cloudwatch_logs_exports

  # Static parameter-group values land on pending-reboot; we apply those
  # during `maintenance_window` rather than immediately so a terraform
  # apply doesn't trigger a surprise reboot. Dynamic values still apply
  # immediately because the parameter group itself sets `apply_method
  # = immediate` on those.
  apply_immediately = var.apply_immediately

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
