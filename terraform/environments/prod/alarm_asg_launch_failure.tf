# asgalarm1 (spec: dev/dev-asgalarm1-…) — alert when an instance launch fails.
#
# AWS already writes the diagnosis and nobody reads it. Measured 2026-09-24:
# 756 failed launch activities across the two parser ASGs (540 spot, 216
# on-demand) since 2026-09-23, each carrying its root cause verbatim, with
# zero alerts and zero reads. Both production incidents this week were named
# in plain English at the moment they happened:
#
#   VcpuLimitExceeded - ...your current vCPU limit of 0...
#   UnfulfillableCapacity - Unable to fulfill capacity due to your request
#     configuration.
#
# The job never failed. It stayed RUNNABLE, the queue stayed VALID, and
# desiredvCpus stayed an ordinary 4 — the failure lived one layer below
# everything anyone was watching.
#
# WHY EVENTBRIDGE AND NOT A METRIC ALARM. Verified 2026-09-24: all three
# ASGs in this account report `EnabledMetrics: []`, so there is no ASG
# metric to alarm on, and Batch owns these ASGs so we cannot enable them.
# EC2 Auto Scaling does emit `EC2 Instance Launch Unsuccessful` to the
# default event bus. The account had zero EventBridge rules before this.
#
# NOT SCOPED TO THE PARSER ASGs, deliberately. Batch regenerates these names
# on every compute-environment replacement (twice already), so a name-scoped
# rule would silently stop matching. Any failed launch in this account is
# worth knowing about.

resource "aws_cloudwatch_log_group" "asg_launch_failure" {
  name              = "/aws/events/${local.project}-${local.environment}-asg-launch-failure"
  retention_in_days = 30
  tags = {
    Name        = "${local.project}-${local.environment}-asg-launch-failure"
    Environment = local.environment
    Project     = local.project
  }
}

# EventBridge needs an explicit resource policy to write to a log group.
data "aws_iam_policy_document" "events_to_logs" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.asg_launch_failure.arn}:*"]
  }
}

resource "aws_cloudwatch_log_resource_policy" "events_to_logs" {
  policy_name     = "${local.project}-${local.environment}-events-to-logs"
  policy_document = data.aws_iam_policy_document.events_to_logs.json
}

resource "aws_cloudwatch_event_rule" "asg_launch_failure" {
  name        = "${local.project}-${local.environment}-asg-launch-failure"
  description = "Failed EC2 Auto Scaling launches (asgalarm1). Carries StatusMessage verbatim."
  event_pattern = jsonencode({
    source        = ["aws.autoscaling"]
    "detail-type" = ["EC2 Instance Launch Unsuccessful"]
  })
}

# The log group is the durable record: it holds the full event JSON, so the
# exact StatusMessage for any incident is one query away even though the
# alarm body below carries the two known messages rather than the live one.
resource "aws_cloudwatch_event_target" "asg_launch_failure_logs" {
  rule = aws_cloudwatch_event_rule.asg_launch_failure.name
  arn  = aws_cloudwatch_log_group.asg_launch_failure.arn
}

# ONE filter on the event's source rather than per-cause filters on
# $.detail.StatusMessage. That JSON path is the one thing here that cannot be
# verified before a real event lands, and if it were wrong every per-cause
# filter would match nothing and this would be a detector that alerts on
# nothing — the exact failure this spec exists to end. `$.source` is part of
# the EventBridge envelope and is present on every event the rule matches.
# Per-cause enrichment is a follow-up, once a live event has confirmed the
# shape.
resource "aws_cloudwatch_log_metric_filter" "asg_launch_failure" {
  name           = "${local.project}-${local.environment}-asg-launch-failure"
  log_group_name = aws_cloudwatch_log_group.asg_launch_failure.name
  pattern        = "{ $.source = \"aws.autoscaling\" }"

  metric_transformation {
    name      = "AsgLaunchFailure"
    namespace = "${local.project}/${local.environment}"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "asg_launch_failure" {
  alarm_name = "${local.project}-${local.environment}-asg-launch-failure"

  alarm_description = <<-EOT
    EC2 launch FAILED. Jobs sit RUNNABLE forever; Batch does NOT fall through
    to the next compute environment.

    Cause, verbatim, in: aws logs tail /aws/events/palateful-prod-asg-launch-failure --since 30m

    Seen in prod (AWS's wording, 2026-09-24):
    1. "VcpuLimitExceeded - You have requested more vCPU capacity than your
       current vCPU limit of 0 allows for the instance bucket that the
       specified instance type belongs to."
       -> quota L-DB2E81BA is 0. See MANUAL.md; request 32, floor 8.
    2. "UnfulfillableCapacity - Unable to fulfill capacity due to your request
       configuration. Please adjust your request and try again."
       -> no spot capacity for these instance types/AZs. See azwide1.

    If the logged message is neither, this text is stale: the log group is
    authoritative.
  EOT

  namespace   = aws_cloudwatch_log_metric_filter.asg_launch_failure.metric_transformation[0].namespace
  metric_name = aws_cloudwatch_log_metric_filter.asg_launch_failure.metric_transformation[0].name
  statistic   = "Sum"

  # RATE LIMITING, which is an acceptance criterion and not a nicety.
  # Measured 2026-09-24: one failure roughly every 60-160s, in bursts of two
  # or three per attempt — 540 in 24h on spot alone. A rule that targeted SNS
  # directly would send one email per event and be muted within the hour,
  # which is a detector whose output reaches someone who stopped listening.
  #
  # A 15-minute Sum with a single evaluation period transitions to ALARM once
  # and stays there for the life of the incident: ONE email per incident, plus
  # one on recovery, regardless of whether the window held 1 failure or 540.
  period              = 900
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  # notBreaching, and the opposite choice from alarm_fail_open.tf on purpose.
  #
  # There, absence of log lines is ambiguous — a dead API and a healthy one
  # both produce no fail-open lines — so `breaching` is correct. Here the log
  # group receives events ONLY when a launch fails, so no datapoints genuinely
  # means no failed launches. Absence is the healthy state.
  #
  # KNOWN LIMITATION, stated rather than hidden: that also means a BROKEN
  # rule looks identical to a quiet one. If the EventBridge rule is deleted or
  # loses its log-group permission, this alarm sits green forever. No setting
  # of treat_missing_data can distinguish those two, because the alarm cannot
  # see its own input path — closing it needs a separate liveness check, not a
  # different threshold here.
  treat_missing_data = "notBreaching"

  alarm_actions = [module.alerts.topic_arn]
  ok_actions    = [module.alerts.topic_arn]

  tags = {
    Name        = "${local.project}-${local.environment}-asg-launch-failure"
    Environment = local.environment
    Project     = local.project
  }
}
