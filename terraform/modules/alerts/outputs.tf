output "topic_arn" {
  description = "ARN of the alert topic. Use as alarm_actions / ok_actions on every alarm."
  value       = aws_sns_topic.alerts.arn
}

output "topic_name" {
  description = "Name of the alert topic."
  value       = aws_sns_topic.alerts.name
}
