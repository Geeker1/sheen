resource "aws_sns_topic" "alarms" {
  name = "${var.name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# The pipeline logs JSON; every failed stage emits {"event": "run.failed"}.
resource "aws_cloudwatch_log_metric_filter" "pipeline_failed" {
  name           = "${var.name}-pipeline-failed"
  log_group_name = aws_cloudwatch_log_group.pipeline.name
  pattern        = "{ $.event = \"run.failed\" }"

  metric_transformation {
    name          = "PipelineRunFailed"
    namespace     = "Sheen"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "pipeline_failed" {
  alarm_name          = "${var.name}-pipeline-failed"
  alarm_description   = "A pipeline stage failed. Query ops.pipeline_runs for the error."
  namespace           = "Sheen"
  metric_name         = "PipelineRunFailed"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = aws_lb.main.arn_suffix }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
