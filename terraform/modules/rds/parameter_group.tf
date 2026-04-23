# Parameter group — palateful-prod-pg16-perf (pim-2, 2026-04-21; aam-1, 2026-04-23)
#
# Cost delta: $0/mo (parameter groups are free). Performance Insights is
# free for 6 months on t4g.small, then ~$2/mo inside NFR29's $50 cap.
#
# STATIC params (require reboot; land on next maintenance window):
#   - shared_buffers      = 256MB
#   - max_connections     = 100  (aam-1: raised 80 → 100 to accommodate
#                                 dual sync+async pool during migration;
#                                 shrinks back after aam-24 pool-shrink)
#
# DYNAMIC params (hot-apply, no reboot required):
#   - work_mem                     = 8MB
#   - maintenance_work_mem         = 128MB
#   - effective_cache_size         = 1500MB
#   - log_min_duration_statement   = 100  (ms — every query >100ms hits
#                                          the slow-query log)
#
# `apply_immediately=false` on the RDS instance means static params sit
# on `pending-reboot` until the next maintenance window applies them.
# Dynamic params take effect as soon as the parameter group associates.
#
# Rollback: delete this file + the parameter_group_name wiring in
# main.tf. The instance falls back to the default postgres16 parameter
# group; static params require one reboot to unwind.

resource "aws_db_parameter_group" "perf" {
  name        = "${var.project}-${var.environment}-pg16-perf"
  family      = "postgres16"
  description = "Palateful ${var.environment} perf-tuned parameters (pim-2)."

  # ─── Static (reboot required) ───

  parameter {
    name         = "shared_buffers"
    value        = "32768" # 32768 * 8KB = 256MB
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "max_connections"
    value        = "100"
    apply_method = "pending-reboot"
  }

  # ─── Dynamic (hot-apply) ───

  parameter {
    name         = "work_mem"
    value        = "8192" # 8192 KB = 8MB
    apply_method = "immediate"
  }

  parameter {
    name         = "maintenance_work_mem"
    value        = "131072" # 131072 KB = 128MB
    apply_method = "immediate"
  }

  parameter {
    name         = "effective_cache_size"
    value        = "192000" # 192000 * 8KB = 1500MB
    apply_method = "immediate"
  }

  parameter {
    name         = "log_min_duration_statement"
    value        = "100"
    apply_method = "immediate"
  }

  tags = {
    Name        = "${var.project}-${var.environment}-pg16-perf"
    Environment = var.environment
    Project     = var.project
  }

  lifecycle {
    create_before_destroy = true
  }
}
