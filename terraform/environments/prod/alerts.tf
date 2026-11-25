# G1: the alert topic every prod alarm publishes to.
# Reference it as module.alerts.topic_arn from your own alarm_*.tf file here.
# Do not add a subscription to this file; see modules/alerts/main.tf.
module "alerts" {
  source = "../../modules/alerts"

  environment = local.environment
  project     = local.project
}

output "alerts_topic_arn" {
  description = "ARN of the prod alert topic (palateful-prod-alerts)."
  value       = module.alerts.topic_arn
}

output "alerts_topic_name" {
  description = "Name of the prod alert topic."
  value       = module.alerts.topic_name
}
