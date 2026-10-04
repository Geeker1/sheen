terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.82.0"
    }
  }

  # Remote state. Create the bucket/table once, then `terraform init`.
  backend "s3" {
    bucket         = "sheen-terraform-state"
    key            = "sheen/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "sheen-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "sheen"
      ManagedBy = "terraform"
    }
  }
}
