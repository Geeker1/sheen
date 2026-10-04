output "api_url" {
  value = "${local.https ? "https" : "http"}://${aws_lb.main.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}

output "run_migrations" {
  description = "Command to apply migrations as a one-off Fargate task."
  value = join(" ", [
    "aws ecs run-task --cluster ${aws_ecs_cluster.main.name}",
    "--task-definition ${aws_ecs_task_definition.pipeline.family}",
    "--launch-type FARGATE",
    "--network-configuration 'awsvpcConfiguration={subnets=[${join(",", aws_subnet.public[*].id)}],securityGroups=[${aws_security_group.app.id}],assignPublicIp=ENABLED}'",
    "--overrides '{\"containerOverrides\":[{\"name\":\"pipeline\",\"command\":[\"sheen\",\"migrate\"]}]}'",
  ])
}
