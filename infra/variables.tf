variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "name" {
  description = "Prefix for resource names."
  type        = string
  default     = "sheen"
}

variable "image_tag" {
  description = "Tag of the application image in ECR to deploy."
  type        = string
  default     = "latest"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "pipeline_schedule" {
  description = "When the ingest/validate/analyse job runs (EventBridge Scheduler expression)."
  type        = string
  default     = "cron(0 3 ? * MON *)" # weekly, Monday 03:00 UTC
}

variable "certificate_arn" {
  description = "ACM certificate for HTTPS on the load balancer. Leave empty for HTTP only."
  type        = string
  default     = ""
}

variable "alarm_email" {
  description = "Where pipeline failure alarms are sent. Leave empty to skip the subscription."
  type        = string
  default     = ""
}
