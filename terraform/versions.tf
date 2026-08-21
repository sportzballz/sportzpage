terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "runmypool-terraform-state-739444271939"
    key          = "production/thedailysportspage.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = local.tags
  }
}
