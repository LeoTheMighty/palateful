# Development environment configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # For dev, use local state. For prod, use S3 backend.
  # backend "s3" {
  #   bucket = "palateful-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "dev"
      Project     = "palateful"
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

locals {
  environment = "dev"
  project     = "palateful"
}

# VPC
module "vpc" {
  source = "../../modules/vpc"

  environment        = local.environment
  project            = local.project
  cidr_block         = "10.0.0.0/16"
  availability_zones = ["${var.aws_region}a", "${var.aws_region}b"]
}

# S3 Buckets for OCR
module "s3" {
  source = "../../modules/s3"

  environment = local.environment
  project     = local.project
}

# ECR Repository
module "ecr" {
  source = "../../modules/ecr"

  environment = local.environment
  project     = local.project
}

# IAM Roles
module "iam" {
  source = "../../modules/iam"

  environment            = local.environment
  project                = local.project
  ocr_inputs_bucket_arn  = module.s3.ocr_inputs_bucket_arn
  ocr_outputs_bucket_arn = module.s3.ocr_outputs_bucket_arn
  ecr_repository_arn     = module.ecr.repository_arn
}

# Batch Compute Environment
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
  max_vcpus                  = 8  # Lower for dev
}

# Outputs
output "ecr_repository_url" {
  value       = module.ecr.repository_url
  description = "ECR repository URL for OCR container"
}

output "ocr_inputs_bucket" {
  value       = module.s3.ocr_inputs_bucket_name
  description = "S3 bucket for OCR input images"
}

output "ocr_outputs_bucket" {
  value       = module.s3.ocr_outputs_bucket_name
  description = "S3 bucket for OCR output JSON"
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
