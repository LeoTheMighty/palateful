# Service Quotas for GPU instances

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "gpu_spot_vcpus" {
  type        = number
  default     = 8
  description = "Desired vCPU quota for G/VT Spot instances"
}

# Request quota increase for G and VT Spot Instance Requests
# This is required for g4dn.xlarge (4 vCPUs) and g5.xlarge (4 vCPUs) instances
resource "aws_servicequotas_service_quota" "gpu_spot_vcpus" {
  quota_code   = "L-3819A6DF" # All G and VT Spot Instance Requests
  service_code = "ec2"
  value        = var.gpu_spot_vcpus
}

output "gpu_spot_quota_value" {
  value       = aws_servicequotas_service_quota.gpu_spot_vcpus.value
  description = "Approved GPU Spot vCPU quota"
}
