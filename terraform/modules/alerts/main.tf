# G1 — the alert push channel (spec: dev/dev-alrt1-…).
#
# Every alarm in terraform/environments/prod/ publishes here. Before this,
# nothing in the AWS account could reach a human: zero alarms, zero
# EventBridge rules, zero metric filters, and one SNS topic with no
# subscribers (obsgap1 §1).
#
# DELIBERATELY NO SUBSCRIPTION IN TERRAFORM. The subscriber's address must not
# appear in this public repo, in `terraform plan` output (CI job logs are
# public too), or in state. The email subscription is created once, by hand,
# outside Terraform. This is the same split as modules/secrets: Terraform owns
# the container and a human supplies the sensitive value.
#
# Consequence to keep in view: if that subscription is ever deleted, nothing
# here recreates it and every alarm publishes into a void. absal1 (U3, the
# absence alert) is what catches that. Land them together.

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-${var.environment}-alerts"

  tags = {
    Name        = "${var.project}-${var.environment}-alerts"
    Environment = var.environment
    Project     = var.project
  }
}

# Let CloudWatch alarms publish to the topic. Without this statement an
# alarm can be wired to the topic, reach ALARM, and still deliver nothing,
# because SNS rejects the publish.
data "aws_iam_policy_document" "alerts" {
  statement {
    sid     = "AllowCloudWatchAlarmsToPublish"
    effect  = "Allow"
    actions = ["sns:Publish"]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    resources = [aws_sns_topic.alerts.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts.json
}
