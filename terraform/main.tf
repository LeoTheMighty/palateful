# Palateful Infrastructure
# Use with: terraform apply -var-file=development.tfvars (or production.tfvars)

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration:
  # - Dev: Uses local state (default)
  # - Prod: Uses S3 backend via -backend-config=backend-prod.hcl
  #
  # To switch backends, run: terraform init -reconfigure -backend-config=backend-prod.hcl
}

# Variables
variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "max_vcpus" {
  type        = number
  default     = 8
  description = "Maximum vCPUs for Batch compute environment"
}

# Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project
      ManagedBy   = "terraform"
    }
  }
}

# Modules
module "vpc" {
  source = "./modules/vpc"

  environment        = var.environment
  project            = var.project
  cidr_block         = "10.0.0.0/16"
  availability_zones = ["${var.aws_region}a", "${var.aws_region}b"]
}

module "s3" {
  source = "./modules/s3"

  environment = var.environment
  project     = var.project
}

module "ecr" {
  source = "./modules/ecr"

  environment = var.environment
  project     = var.project
}

module "iam" {
  source = "./modules/iam"

  environment               = var.environment
  project                   = var.project
  parser_inputs_bucket_arn  = module.s3.parser_inputs_bucket_arn
  parser_outputs_bucket_arn = module.s3.parser_outputs_bucket_arn
  ecr_repository_arn        = module.ecr.repository_arn
}

module "batch" {
  source = "./modules/batch"

  environment                = var.environment
  project                    = var.project
  aws_region                 = var.aws_region
  batch_instance_profile_arn = module.iam.batch_instance_profile_arn
  batch_service_role_arn     = module.iam.batch_service_role_arn
  batch_job_role_arn         = module.iam.batch_job_role_arn
  spot_fleet_role_arn        = module.iam.spot_fleet_role_arn
  ecr_repository_url         = module.ecr.repository_url
  subnet_ids                 = module.vpc.public_subnet_ids
  security_group_ids         = [module.vpc.batch_security_group_id]
  max_vcpus                  = var.max_vcpus
}

# Outputs
output "ecr_repository_url" {
  value       = module.ecr.repository_url
  description = "ECR repository URL for parser container"
}

output "parser_inputs_bucket" {
  value       = module.s3.parser_inputs_bucket_name
  description = "S3 bucket for parser input images"
}

output "parser_outputs_bucket" {
  value       = module.s3.parser_outputs_bucket_name
  description = "S3 bucket for parser output JSON"
}

output "batch_job_queue" {
  value       = module.batch.job_queue_name
  description = "Batch job queue name"
}

output "batch_job_definition" {
  value       = module.batch.job_definition_name
  description = "Batch job definition name"
}

output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC ID"
}

output "api_service_policy_arn" {
  value       = module.iam.api_service_policy_arn
  description = "IAM policy ARN for API service"
}
