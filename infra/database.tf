resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_parameter_group" "main" {
  name   = "${var.name}-pg16"
  family = "postgres16"

  # Log slow statements so spatial queries that regress show up in CloudWatch.
  parameter {
    name  = "log_min_duration_statement"
    value = "2000"
  }
}

# PostGIS ships with RDS Postgres; the first migration runs CREATE EXTENSION.
resource "aws_db_instance" "main" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_encrypted     = true

  db_name  = "sheen"
  username = "sheen"
  # RDS generates and rotates the password in Secrets Manager.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false

  backup_retention_period         = 7
  enabled_cloudwatch_logs_exports = ["postgresql"]
  deletion_protection             = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.name}-final"
}
