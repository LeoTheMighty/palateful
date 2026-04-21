# Application Load Balancer with ACM SSL

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
  description = "Subnet IDs for ALB"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for ALB"
}

variable "domain_name" {
  type        = string
  default     = ""
  description = "Domain name for ACM certificate (e.g. api.palateful.app). Empty to skip HTTPS."
}

# ALB
resource "aws_lb" "main" {
  name               = "${var.project}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = var.security_group_ids
  subnets            = var.subnet_ids

  tags = {
    Name        = "${var.project}-alb-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# Target group for API service
resource "aws_lb_target_group" "api" {
  name        = "${var.project}-api-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path = "/v1/health"
    port = "8000"
    protocol = "HTTP"
    # pim-4b (2026-04-21): 30/5 → 60/3. Halves health-check volume on
    # the hot path; hung-task detection still fires within 2 min.
    # ECS deployment circuit breaker still gates failed deploys, so
    # the 1-minute longer window is safe.
    interval = 60
    timeout  = 3
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = {
    Name        = "${var.project}-api-tg-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# ACM Certificate (conditional on domain_name)
resource "aws_acm_certificate" "main" {
  count             = var.domain_name != "" ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project}-cert-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# HTTP listener — forward when no cert, redirect to HTTPS when cert exists
resource "aws_lb_listener" "http" {
  count             = var.domain_name != "" ? 0 : 1
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS listener (conditional on domain_name)
resource "aws_lb_listener" "https" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Outputs

output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "ALB DNS name"
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "alb_zone_id" {
  value = aws_lb.main.zone_id
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "acm_certificate_arn" {
  value = try(aws_acm_certificate.main[0].arn, "")
}

output "acm_validation_records" {
  value = try(
    [for dvo in aws_acm_certificate.main[0].domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }],
    []
  )
  description = "DNS records to add in Cloudflare for ACM certificate validation"
}
