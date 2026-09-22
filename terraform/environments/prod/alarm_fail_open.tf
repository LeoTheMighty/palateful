# G11 (spec: dev/dev-dfrcp1-…) — alarm when the DB probe fails open.
#
# rsh102 answers /v1/health with 200 when it cannot tell whether the database
# is healthy: a broken pool, an unreachable host or an unclassified driver
# error all "fail open" rather than drain the service. That is the right
# trade — draining on a condition a restart cannot fix takes the service down
# permanently (selfheal1) — but it means a total DB outage reads
# {"status": "ok"} to every external check. The log line is the ONLY trace.
#
# The phrase `failing open` is therefore a contract, not a log message. It is
# emitted by every fail-open path in `db_probe.py` and `health_router.py`
# (4 on main; 9 once selfheal1 lands). Match on the phrase, never on line
# numbers — they move.
#
# Two tests hold the two halves of that contract, and they fail on different
# mistakes. Change the pattern below and you must change both:
#
#   * behaviour — selfheal1's `test_db_probe.py::
#     test_every_fail_open_verdict_logs_failing_open` and
#     `test_probe_sync_survives_a_classifier_failure_on_an_absent_url` DRIVE
#     the paths and assert the phrase. They catch a reword.
#   * source — `libraries/utils/test/test_fail_open_phrase_sweep.py`
#     ENUMERATES fail-open verdict sites and asserts none lacks the phrase.
#     It catches a NEW branch that never logs it, which every driving test
#     passes straight through. selfheal1 found exactly that in `probe_sync`.

resource "aws_cloudwatch_log_metric_filter" "api_fail_open" {
  name           = "${local.project}-${local.environment}-api-fail-open"
  log_group_name = module.ecs.api_log_group_name

  # Quoted term = literal substring match, case-sensitive. The phrase sits
  # inside longer messages, so no wildcards are needed.
  pattern = "\"failing open\""

  metric_transformation {
    name      = "ApiDbProbeFailOpen"
    namespace = "${local.project}/${local.environment}"
    value     = "1"
    # Explicit zero so the metric reports 0 for quiet periods instead of no
    # data; without it the alarm sits in INSUFFICIENT_DATA and treat_missing
    # has to carry the logic.
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_fail_open" {
  alarm_name        = "${local.project}-${local.environment}-api-fail-open"
  alarm_description = <<-EOT
    The API database probe failed open: /v1/health is returning 200 while the
    probe could not confirm the database is healthy. A total DB outage looks
    healthy to every external check while this is firing.

    Look at: bin/prod-logs, filter `failing open`, and the four branches in
    db_probe.py / health_router.py. Spec: dev/dev-dfrcp1-…
  EOT

  namespace   = aws_cloudwatch_log_metric_filter.api_fail_open.metric_transformation[0].namespace
  metric_name = aws_cloudwatch_log_metric_filter.api_fail_open.metric_transformation[0].name
  statistic   = "Sum"
  period      = 300

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  # SILENCE IS NOT HEALTH (4f's audit of this PR).
  #
  # A metric filter only sees log events. If the API stops logging — task
  # dead, log driver broken, log group renamed — "no fail-open lines" and
  # "no API at all" produce the same picture: no datapoints. Under
  # `notBreaching` this alarm would sit green through a total outage, which
  # is the exact shape of failure this story exists to end.
  #
  # `breaching` is safe here because the metric inherits the log group's
  # continuity: `default_value = 0` emits a datapoint for every log event
  # the filter processes, matching or not. So data exists whenever the API
  # logs at all, and missing data means it isn't.
  #
  # MEASURED before choosing (2026-09-22, 24h of AWS/Logs IncomingLogEvents
  # on this log group at 300s): 288 datapoints out of 288 possible buckets,
  # ~20-23 events per bucket, no gaps — including across the :64 rollout at
  # 11:09-11:16 that day. A deploy does not produce a missing bucket, so
  # this does not trade a blind spot for a false-alarm generator.
  #
  # Chosen over an absence companion alarm (the G2 shape) deliberately: the
  # companion would be a second alarm to wire, subscribe and verify for the
  # same signal, and an unverified second alarm is how the first blind spot
  # got here. Revisit if the log stream ever becomes genuinely bursty — then
  # the companion, on a longer window, is the better instrument.
  treat_missing_data = "breaching"

  alarm_actions = [module.alerts.topic_arn]
  ok_actions    = [module.alerts.topic_arn]

  tags = {
    Environment = local.environment
    Project     = local.project
  }
}
