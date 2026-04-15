# Palateful Production Environment

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {}
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "api_image_tag" {
  type    = string
  default = "latest"
}

variable "worker_image_tag" {
  type    = string
  default = "latest"
}

variable "migrator_image_tag" {
  type    = string
  default = "latest"
}

locals {
  environment = "prod"
  project     = "palateful"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = local.environment
      Project     = local.project
      ManagedBy   = "terraform"
    }
  }
}

# ─── Networking ───

module "vpc" {
  source = "../../modules/vpc"

  environment          = local.environment
  project              = local.project
  cidr_block           = "10.1.0.0/16"
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
  create_ecs_resources = true
}

# ─── Storage ───

module "s3" {
  source = "../../modules/s3"

  environment = local.environment
  project     = local.project
}

module "ecr" {
  source = "../../modules/ecr"

  environment             = local.environment
  project                 = local.project
  additional_repositories = ["api", "worker", "migrator"]
}

# ─── Secrets ───

module "secrets" {
  source = "../../modules/secrets"

  environment = local.environment
  project     = local.project
}

# ─── IAM ───

module "iam" {
  source = "../../modules/iam"

  environment               = local.environment
  project                   = local.project
  parser_inputs_bucket_arn  = module.s3.parser_inputs_bucket_arn
  parser_outputs_bucket_arn = module.s3.parser_outputs_bucket_arn
  ecr_repository_arn        = module.ecr.repository_arn
  create_ecs_roles          = true
  sqs_queue_arns            = [module.sqs.celery_queue_arn, module.sqs.celery_dlq_arn]
  secrets_arns = concat(
    module.secrets.all_secret_arns,
    [
      "arn:aws:secretsmanager:us-east-1:592349850338:secret:palateful-firebase-prod-jy4C1N",
      module.rds.db_master_secret_arn,
    ],
  )
}

# ─── Database ───

module "rds" {
  source = "../../modules/rds"

  environment        = local.environment
  project            = local.project
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.public_subnet_ids
  security_group_ids = [module.vpc.rds_security_group_id]
  instance_class     = "db.t4g.micro"
  allocated_storage  = 20
}

# ─── Queues ───

module "sqs" {
  source = "../../modules/sqs"

  environment = local.environment
  project     = local.project
}

# ─── Parser Pipeline ───

module "quotas" {
  source = "../../modules/quotas"

  environment    = local.environment
  project        = local.project
  gpu_spot_vcpus = 32
}

module "batch" {
  source = "../../modules/batch"

  environment                = local.environment
  project                    = local.project
  aws_region                 = var.aws_region
  batch_instance_profile_arn = module.iam.batch_instance_profile_arn
  batch_service_role_arn     = module.iam.batch_service_role_arn
  batch_job_role_arn         = module.iam.batch_job_role_arn
  spot_fleet_role_arn        = module.iam.spot_fleet_role_arn
  ecr_repository_url         = module.ecr.repository_url
  subnet_ids                 = module.vpc.public_subnet_ids
  security_group_ids         = [module.vpc.batch_security_group_id]
  max_vcpus                  = 32
}

# ─── Load Balancer ───

module "alb" {
  source = "../../modules/alb"

  environment        = local.environment
  project            = local.project
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.public_subnet_ids
  security_group_ids = [module.vpc.alb_security_group_id]
  domain_name        = "api.palateful.app"
}

# ─── ECS Services ───

module "ecs" {
  source = "../../modules/ecs"

  environment            = local.environment
  project                = local.project
  aws_region             = var.aws_region
  subnet_ids             = module.vpc.public_subnet_ids
  security_group_ids     = [module.vpc.ecs_security_group_id]
  execution_role_arn     = module.iam.ecs_execution_role_arn
  api_task_role_arn      = module.iam.ecs_api_task_role_arn
  worker_task_role_arn   = module.iam.ecs_worker_task_role_arn
  migrator_task_role_arn = module.iam.ecs_migrator_task_role_arn
  api_image              = "${module.ecr.additional_repository_urls["api"]}:${var.api_image_tag}"
  worker_image           = "${module.ecr.additional_repository_urls["worker"]}:${var.worker_image_tag}"
  migrator_image         = "${module.ecr.additional_repository_urls["migrator"]}:${var.migrator_image_tag}"
  api_target_group_arn   = module.alb.api_target_group_arn

  # DB credentials: ECS pulls DB_PASSWORD directly from the RDS-managed
  # Secrets Manager secret at task start. Host/port/name/user are plain
  # env vars because they're not secret. This kills the drift vector we
  # hit when DATABASE_URL lived in a separately-maintained secret.
  db_master_secret_arn = module.rds.db_master_secret_arn
  db_host              = module.rds.db_address
  db_port              = module.rds.db_port
  db_name              = module.rds.db_name
  db_username          = module.rds.db_username

  auth0_secret_arn      = module.secrets.auth0_secret_arn
  openai_secret_arn     = module.secrets.openai_secret_arn
  celery_queue_prefix   = module.sqs.celery_queue_prefix
  parser_inputs_bucket  = module.s3.parser_inputs_bucket_name
  parser_outputs_bucket = module.s3.parser_outputs_bucket_name
  batch_job_queue       = module.batch.job_queue_name
  batch_job_definition  = module.batch.job_definition_name
  firebase_secret_arn   = "arn:aws:secretsmanager:us-east-1:592349850338:secret:palateful-firebase-prod-jy4C1N"
}

# ─── Outputs ───

output "alb_dns_name" {
  value       = module.alb.alb_dns_name
  description = "ALB DNS name — your API endpoint"
}

output "acm_validation_records" {
  value       = module.alb.acm_validation_records
  description = "Add these DNS records in Cloudflare to validate the ACM certificate"
}

output "rds_endpoint" {
  value       = module.rds.db_endpoint
  description = "RDS endpoint (host:port)"
}

output "db_master_secret_arn" {
  value       = module.rds.db_master_secret_arn
  description = "ARN of RDS auto-managed password secret"
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecr_api_url" {
  value = module.ecr.additional_repository_urls["api"]
}

output "ecr_worker_url" {
  value = module.ecr.additional_repository_urls["worker"]
}

output "ecr_migrator_url" {
  value = module.ecr.additional_repository_urls["migrator"]
}

output "ecr_parser_url" {
  value = module.ecr.repository_url
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "public_subnet_ids" {
  value = module.vpc.public_subnet_ids
}

output "ecs_security_group_id" {
  value = module.vpc.ecs_security_group_id
}

output "sqs_celery_queue_url" {
  value = module.sqs.celery_queue_url
}

output "parser_inputs_bucket" {
  value = module.s3.parser_inputs_bucket_name
}

output "parser_outputs_bucket" {
  value = module.s3.parser_outputs_bucket_name
}

output "batch_job_queue" {
  value = module.batch.job_queue_name
}

output "batch_job_definition" {
  value = module.batch.job_definition_name
}

output "migrator_task_definition_arn" {
  value = module.ecs.migrator_task_definition_arn
}
