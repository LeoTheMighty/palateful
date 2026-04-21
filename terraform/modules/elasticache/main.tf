# ElastiCache Redis — single-node cache.t4g.micro
#
# pim-5 (2026-04-21). Sole use case: Auth0 JWKS cache warming across
# task restarts + single-flight dedupe across concurrent task
# cold-starts. Fail-open: Auth0Verifier falls back to module-global
# in-memory cache if Redis is unreachable — no request can fail
# because of Redis.
#
# No multi-AZ, no replicas, one node. Acceptable ONLY because the
# consumer (Auth0 JWKS cache) is fail-open. Any future use of Redis
# for application data requires revisiting multi-AZ.
#
# Cost delta: ≈ +$1/mo for the cache.t4g.micro node.

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-cache-${var.environment}"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.project}-cache-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_security_group" "cache" {
  name        = "${var.project}-cache-sg-${var.environment}"
  description = "ElastiCache Redis — allow ingress from API + worker SGs on 6379"
  vpc_id      = var.vpc_id

  # Each allowed SG gets its own ingress rule so adding/removing is
  # clean (the alternative — a single rule with a list — is valid but
  # less readable and terraform diffs are noisier).
  dynamic "ingress" {
    for_each = toset(var.allowed_security_group_ids)
    content {
      description     = "Redis from allowed SG"
      from_port       = 6379
      to_port         = 6379
      protocol        = "tcp"
      security_groups = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-cache-sg-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project}-cache-${var.environment}"
  description          = "Palateful Redis for Auth0 JWKS cache (pim-5)"

  node_type                  = var.node_type
  port                       = 6379
  parameter_group_name       = "default.redis7"
  engine                     = "redis"
  engine_version             = "7.1"
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.cache.id]

  # No auth_token / encryption in transit — Redis lives in a private
  # VPC subnet behind SG-gated access. If we ever move Redis to
  # multi-AZ or add public-facing replicas, revisit both.
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false

  apply_immediately = true

  tags = {
    Name        = "${var.project}-cache-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# SSM parameter — SecureString holding the REDIS_URL that ECS tasks
# read at start. Written by terraform from the computed endpoint so no
# manual copy-paste.
resource "aws_ssm_parameter" "redis_url" {
  name        = "/${var.project}/${var.environment}/redis_url"
  description = "Redis connection URL for API + worker tasks (pim-5)"
  type        = "SecureString"
  value       = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}
