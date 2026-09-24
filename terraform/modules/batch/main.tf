# AWS Batch compute environment for parser with Spot GPU instances

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "batch_instance_profile_arn" {
  type        = string
  description = "ARN of Batch instance profile"
}

variable "batch_service_role_arn" {
  type        = string
  description = "ARN of Batch service role"
}

variable "batch_job_role_arn" {
  type        = string
  description = "ARN of Batch job role"
}

variable "spot_fleet_role_arn" {
  type        = string
  description = "ARN of Spot Fleet role"
}

variable "ecr_repository_url" {
  type        = string
  description = "ECR repository URL for parser container"
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Image tag to deploy for the parser container (SHA in CI, 'latest' for local)"
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of subnet IDs for compute environment"
}

variable "security_group_ids" {
  type        = list(string)
  description = "List of security group IDs for compute environment"
}

variable "max_vcpus" {
  type        = number
  default     = 16
  description = "Maximum vCPUs for compute environment"
}

variable "max_ondemand_vcpus" {
  type        = number
  default     = 8
  description = "Maximum vCPUs for the on-demand fallback compute environment (pcap1). 8 = two concurrent 4-vCPU GPU jobs; bounds the cost of a spot outage."
}

variable "root_volume_size_gb" {
  type        = number
  default     = 100
  description = "Root EBS volume size in GB for Batch instances (must be large enough for GPU container images)"
}

# Launch template with larger root volume for GPU container images
resource "aws_launch_template" "parser_batch" {
  name = "${var.project}-parser-batch-${var.environment}"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.root_volume_size_gb
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tags = {
    Name        = "${var.project}-parser-launch-template"
    Environment = var.environment
    Project     = var.project
  }
}

# Compute Environment - Spot GPU instances
resource "aws_batch_compute_environment" "parser_spot_gpu" {
  compute_environment_name_prefix = "${var.project}-parser-spot-gpu-${var.environment}-"
  type                            = "MANAGED"
  state                           = "ENABLED"
  service_role                    = var.batch_service_role_arn

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_PRICE_CAPACITY_OPTIMIZED"

    min_vcpus     = 0 # Scale to zero when idle
    desired_vcpus = 0 # Start at zero
    max_vcpus     = var.max_vcpus

    # pcap1: widened 2026-09-22. Two instance types is two spot pools, and
    # on 2026-09-22 both were empty for 3+ hours: Leo's import was killed
    # after 187 minutes with three `instance-terminated-no-capacity`
    # closures and never started. Every type here is 1 GPU and >= the job
    # definition's 4 vCPU / 15360 MB, so any of them can run the job;
    # SPOT_PRICE_CAPACITY_OPTIMIZED picks the cheapest with capacity.
    instance_type = [
      "g4dn.xlarge",  # NVIDIA T4,   4 vCPU / 16 GiB
      "g4dn.2xlarge", # NVIDIA T4,   8 vCPU / 32 GiB
      "g5.xlarge",    # NVIDIA A10G, 4 vCPU / 16 GiB
      "g5.2xlarge",   # NVIDIA A10G, 8 vCPU / 32 GiB
      "g6.xlarge",    # NVIDIA L4,   4 vCPU / 16 GiB
    ]

    subnets             = var.subnet_ids
    security_group_ids  = var.security_group_ids
    instance_role       = var.batch_instance_profile_arn
    spot_iam_fleet_role = var.spot_fleet_role_arn

    launch_template {
      launch_template_id = aws_launch_template.parser_batch.id
      version            = "$Latest"
    }

    tags = {
      Name        = "${var.project}-parser-batch"
      Environment = var.environment
      Project     = var.project
    }
  }

  tags = {
    Name        = "${var.project}-parser-compute-env"
    Environment = var.environment
    Project     = var.project
  }

  lifecycle {
    create_before_destroy = true

    # AWS Batch owns desired_vcpus at runtime: it scales the compute
    # environment up to run queued jobs and back down to min_vcpus when idle.
    # The value above is an INITIAL value only ("Start at zero"), so without
    # this every plan proposes resetting whatever Batch has chosen back to 0.
    #
    # bvcpu1 (2026-09-23): measured on `main` while a job sat RUNNABLE —
    # `~ desired_vcpus = 4 -> 0`, an unrelated 1-change plan riding along on
    # any merge. Harmless-looking, and it had been invisible because the value
    # is 0 whenever the queue is idle, which is whenever anyone happened to
    # look. Since tfgate1 (#36) applies Terraform automatically on merge, this
    # would be applied by whichever PR merged next — scaling capacity away
    # from a queued job, or terminating the instance under a running one.
    ignore_changes = [compute_resources[0].desired_vcpus]
  }
}

# On-demand fallback compute environment (pcap1).
#
# Second in the queue's order, so Batch only reaches it when the spot
# environment above cannot provide capacity. Bounded by
# `max_ondemand_vcpus` (default 8 = two concurrent jobs) so a spot outage
# cannot run up an unbounded GPU bill.
#
# Cost, measured from the AWS Pricing API 2026-09-22 (us-east-1, Linux):
# g4dn.xlarge on-demand $0.526/hr, g6.xlarge $0.805, g4dn.2xlarge $0.752,
# g5.xlarge $1.006. Historical successful batches ran 11-13 minutes, so a
# job that falls back costs about $0.11. BEST_FIT_PROGRESSIVE prefers the
# cheapest type that fits.
resource "aws_batch_compute_environment" "parser_ondemand_gpu" {
  compute_environment_name_prefix = "${var.project}-parser-ondemand-gpu-${var.environment}-"
  type                            = "MANAGED"
  state                           = "ENABLED"
  service_role                    = var.batch_service_role_arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"

    min_vcpus     = 0
    desired_vcpus = 0
    max_vcpus     = var.max_ondemand_vcpus

    # Same five types as the spot environment. The fallback should not have
    # a narrower pool than the primary it exists to cover for — g5.2xlarge
    # was omitted by oversight, not by design (caught by palateful-0e in
    # independent re-confirmation).
    instance_type = [
      "g4dn.xlarge",
      "g4dn.2xlarge",
      "g5.xlarge",
      "g5.2xlarge",
      "g6.xlarge",
    ]

    subnets            = var.subnet_ids
    security_group_ids = var.security_group_ids
    instance_role      = var.batch_instance_profile_arn

    launch_template {
      launch_template_id = aws_launch_template.parser_batch.id
      version            = "$Latest"
    }

    tags = {
      Name        = "${var.project}-parser-batch-ondemand"
      Environment = var.environment
      Project     = var.project
    }
  }

  tags = {
    Name        = "${var.project}-parser-compute-env-ondemand"
    Environment = var.environment
    Project     = var.project
  }

  lifecycle {
    # Matches the spot environment. `create_before_destroy` pairs with the
    # name_prefix: any future change that forces replacement builds the new
    # environment first, so the queue is never left pointing at nothing.
    create_before_destroy = true

    # AWS Batch owns desired_vcpus at runtime; without this every unrelated
    # apply plans a reset (see bvcpu1).
    ignore_changes = [compute_resources[0].desired_vcpus]
  }
}

# Job Queue
resource "aws_batch_job_queue" "parser" {
  name     = "${var.project}-parser-queue-${var.environment}"
  state    = "ENABLED"
  priority = 1

  # odback1 (2026-09-24): ON-DEMAND FIRST, spot second. Restores #76's
  # ordering now that `L-DB2E81BA` has actually been granted.
  #
  #   L-DB2E81BA  "Running On-Demand G and VT instances"  = 32
  #   L-3819A6DF  "All G and VT Spot Instance Requests"   = 32
  #
  # `spotback1` put spot first **only** because the on-demand quota was 0
  # and the environment could not launch anything. That reason has expired:
  # AWS granted case 179026203300222 on 2026-09-24. **The TEMPORARY markers
  # are removed because the condition they described is gone**, not because
  # anyone changed their mind about the design.
  #
  # Why on-demand leads, from #76: Batch reaches order 2 only when order 1
  # **cannot allocate**, not when it allocates and fails to deliver. Spot
  # first fails open into "queued forever" — observed three times in two
  # days, at 65, 88 and 90+ minutes, against April's ~11.9-minute jobs.
  # On-demand first fails into "slightly more expensive": about **$7.50 a
  # month** at April's real volume (40 jobs, 8.20 GPU-hours; the earlier
  # $4.36 counted only successful runs). Spot stays at order 2 and still
  # absorbs work whenever it has capacity, so the real figure lands below.
  #
  # **Two things that must not be forgotten here, both learned the hard
  # way:**
  #
  # 1. `CASE_CLOSED` does not mean granted. The approval email for this
  #    quota arrived while `Quota.Value` still read **0.0** — AWS states a
  #    30-minute propagation window. Before relying on any quota, read
  #    `service-quotas get-service-quota … --query 'Quota.Value'`.
  # 2. **Order 1 being capable is not the whole story.** Both GPU compute
  #    environments are pinned to `us-east-1a`/`1b`, which score **2** and
  #    **1** for spot placement. On-demand has no placement-score problem,
  #    but the AZ narrowness is inherited by whichever environment leads —
  #    see `azwide1`.
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.parser_ondemand_gpu.arn
  }

  compute_environment_order {
    order               = 2
    compute_environment = aws_batch_compute_environment.parser_spot_gpu.arn
  }

  tags = {
    Name        = "${var.project}-parser-queue"
    Environment = var.environment
    Project     = var.project
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "parser_batch" {
  name              = "/aws/batch/${var.project}-parser-${var.environment}"
  retention_in_days = var.environment == "prod" ? 30 : 7

  tags = {
    Name        = "${var.project}-parser-logs"
    Environment = var.environment
    Project     = var.project
  }
}

# Job Definition
resource "aws_batch_job_definition" "parser" {
  name = "${var.project}-parser-job-${var.environment}"
  type = "container"

  platform_capabilities = ["EC2"]

  # pcap1: 3 attempts with no evaluate_on_exit retried a capacity kill and
  # an application crash identically, and burned all three in 30 minutes
  # against pools that stayed empty for hours. Now: retry the host-level
  # kills (spot reclamation, `instance-terminated-no-capacity`) many
  # times, and stop immediately on anything else so a real crash still
  # fails fast instead of running three times.
  retry_strategy {
    attempts = 10

    evaluate_on_exit {
      action           = "RETRY"
      on_status_reason = "Host EC2*"
    }

    evaluate_on_exit {
      action    = "EXIT"
      on_reason = "*"
    }
  }

  timeout {
    attempt_duration_seconds = 1800 # 30 minutes max
  }

  container_properties = jsonencode({
    image = "${var.ecr_repository_url}:${var.image_tag}"

    resourceRequirements = [
      { type = "VCPU", value = "4" },
      { type = "MEMORY", value = "15360" }, # 15GB (leave headroom for ECS agent/OS)
      { type = "GPU", value = "1" }
    ]

    jobRoleArn = var.batch_job_role_arn

    environment = [
      { name = "MODEL_NAME", value = "tencent/HunyuanOCR" },
      { name = "DEVICE", value = "cuda" },
      { name = "TORCH_DTYPE", value = "float16" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.parser_batch.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "parser"
      }
    }
  })

  tags = {
    Name        = "${var.project}-parser-job-def"
    Environment = var.environment
    Project     = var.project
  }
}

output "compute_environment_arn" {
  value = aws_batch_compute_environment.parser_spot_gpu.arn
}

output "job_queue_arn" {
  value = aws_batch_job_queue.parser.arn
}

output "job_queue_name" {
  value = aws_batch_job_queue.parser.name
}

output "job_definition_arn" {
  value = aws_batch_job_definition.parser.arn
}

output "job_definition_name" {
  value = aws_batch_job_definition.parser.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.parser_batch.name
}
