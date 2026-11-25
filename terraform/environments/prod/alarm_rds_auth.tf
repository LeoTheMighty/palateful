# G2 — RDS auth-failure alarm (dev/dev-obsgap1 §6, item 2; dev/dev-clidet1).
#
# Why: prod Postgres rejected the app's password 573,039 times across six
# episodes between 2026-04-22 and 2026-07-31, and nothing told anyone.
# 04-22 is the earliest observable point, not a proven start: the RDS log
# export (and this log group) only began 2026-04-21 14:50 UTC. The
# app's own error_logs table could not record it: it lives in the database
# that was rejecting the connections. The RDS log export is the only
# recorder that sits outside the thing that broke.
#
# Publishes to the G1 topic (module.alerts, terraform/environments/prod/
# alerts.tf). This file must apply together with or after that module.
#
# All thresholds below come from measurements, not guesses. See the PR for
# the queries.

locals {
  # Mirrors the identifier in modules/rds/main.tf:
  # "${var.project}-db-${var.environment}". AWS names the export group from
  # it. If the RDS identifier ever changes, change this too; the absence
  # alarm below goes into ALARM if the two drift apart.
  rds_postgres_log_group = "/aws/rds/instance/${local.project}-db-${local.environment}/postgresql"
}

# Counts Postgres password-authentication failures.
#
# The pattern is anchored on the FATAL form, two spaces included, exactly as
# RDS writes it:
#   2026-07-30 18:01:01 UTC:10.1.1.175(53456):palateful@palateful:[17132]:FATAL:  password authentication failed for user "palateful"
# The bare phrase would also match slow-query LOG lines whose statement text
# contains it (log_min_duration_statement = 100 ms writes statement text to
# this same log). Anyone investigating an auth outage in SQL would trip the
# alarm. The paired "DETAIL:  Connection matched file ..." line does not
# contain the phrase, so each failure counts once.
#
# default_value = 0 emits a zero for every non-matching line. The export has
# a steady checkpoint heartbeat (>= 5 events every 15 min for 14 days), so
# the metric always has datapoints and the alarm shows OK instead of
# INSUFFICIENT_DATA. That is visible proof the filter is attached and
# evaluating.
resource "aws_cloudwatch_log_metric_filter" "rds_auth_failures" {
  name           = "${local.project}-${local.environment}-rds-auth-failures"
  log_group_name = local.rds_postgres_log_group
  pattern        = "\"FATAL:  password authentication failed\""

  metric_transformation {
    name          = "RdsPasswordAuthFailures"
    namespace     = "Palateful/${local.environment}"
    value         = "1"
    default_value = "0"
  }
}

# Pages when authentication failures persist: at least one failure in each of
# 2 of the last 3 five-minute periods.
#
# Simulated against the real 5-minute series from 2026-04-22 to 2026-09-22:
# pages exactly once per episode (6 of 6), 10 minutes after onset, with 0
# false pages. Within an episode there are no empty 5-minute bins (the
# retry loop fires about every 17 s), so persistence is the signature. A
# single stray failure, such as a mistyped psql password, never pages.
# Rate thresholds were worse:
#   >= 5 per 5 min flaps (9 pages for 6 episodes) and is slow on the low-rate
#   onsets (episode 1 ran at 4 per 5 min, episode 3 started at 2);
#   any single failure pages on a typo.
# Baseline since the outage ended (2026-08-01 to 2026-09-22): 0 FATAL lines
# of any kind.
resource "aws_cloudwatch_metric_alarm" "rds_auth_failures" {
  alarm_name        = "${local.project}-${local.environment}-rds-auth-failures"
  alarm_description = "Postgres is rejecting logins (FATAL: password authentication failed) in 2 of the last 3 five-minute periods. Usually a rotated DB secret the running task has not picked up. Check the RDS postgresql log group and the api/worker task's secret. Spec: dev/dev-clidet1, dev/dev-obsgap1 G2."

  namespace           = "Palateful/${local.environment}"
  metric_name         = "RdsPasswordAuthFailures"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [module.alerts.topic_arn]
  ok_actions    = [module.alerts.topic_arn]

  depends_on = [aws_cloudwatch_log_metric_filter.rds_auth_failures]
}

# Pages when the RDS log export itself goes silent.
#
# The auth alarm above can only see what the export delivers. If the export
# stops, a missing metric reads as notBreaching and the alarm stays green
# while blind. That is the same recorder-depends-on-the-thing-that-broke
# failure that hid the outage from error_logs. Measured over 14 days: every
# hour had events (min 23, median 24), from the checkpoint heartbeat every
# 5 minutes. An hour with zero events has never happened.
#
# treat_missing_data = "breaching": CloudWatch publishes no datapoint for
# a group with no incoming events, so missing data is the failure itself.
resource "aws_cloudwatch_metric_alarm" "rds_log_export_silent" {
  alarm_name        = "${local.project}-${local.environment}-rds-log-export-silent"
  alarm_description = "The RDS postgresql log group received no events for an hour. Normal is ~24/hour from the checkpoint heartbeat. While this is in ALARM, the rds-auth-failures alarm is blind. Check the instance's CloudWatch log exports and instance status."

  namespace           = "AWS/Logs"
  metric_name         = "IncomingLogEvents"
  dimensions          = { LogGroupName = local.rds_postgres_log_group }
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  alarm_actions = [module.alerts.topic_arn]
  ok_actions    = [module.alerts.topic_arn]
}
