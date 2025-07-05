terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local values
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"
  
  name_prefix         = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  
  tags = local.common_tags
}

# Security Groups Module
module "security_groups" {
  source = "./modules/security"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  
  tags = local.common_tags
}

# RDS Module
module "rds" {
  source = "./modules/rds"
  
  name_prefix           = local.name_prefix
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  security_group_ids   = [module.security_groups.rds_security_group_id]
  
  db_instance_class    = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  db_name             = var.db_name
  db_username         = var.db_username
  db_password         = var.db_password
  
  tags = local.common_tags
}

# ElastiCache Module
module "elasticache" {
  source = "./modules/elasticache"
  
  name_prefix        = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.redis_security_group_id]
  
  node_type = var.redis_node_type
  
  tags = local.common_tags
}

# MSK (Kafka) Module
module "msk" {
  source = "./modules/msk"
  
  name_prefix        = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.kafka_security_group_id]
  
  kafka_version    = var.kafka_version
  instance_type    = var.kafka_instance_type
  number_of_nodes  = var.kafka_number_of_nodes
  
  tags = local.common_tags
}

# ECS Cluster Module
module "ecs" {
  source = "./modules/ecs"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  
  alb_security_group_id = module.security_groups.alb_security_group_id
  ecs_security_group_id = module.security_groups.ecs_security_group_id
  
  # Service configurations
  services = {
    gateway = {
      image         = var.gateway_image
      port          = 8000
      cpu           = 256
      memory        = 512
      desired_count = 2
      health_check_path = "/healthz"
    }
    shortener = {
      image         = var.shortener_image
      port          = 8001
      cpu           = 256
      memory        = 512
      desired_count = 2
      health_check_path = "/healthz"
    }
    redirector = {
      image         = var.redirector_image
      port          = 8002
      cpu           = 256
      memory        = 512
      desired_count = 3
      health_check_path = "/healthz"
    }
    analytics = {
      image         = var.analytics_image
      port          = 8003
      cpu           = 256
      memory        = 512
      desired_count = 2
      health_check_path = "/healthz"
    }
  }
  
  # Environment variables
  environment_variables = {
    DATABASE_URL = module.rds.connection_string
    REDIS_URL    = module.elasticache.redis_url
    KAFKA_BOOTSTRAP_SERVERS = module.msk.bootstrap_brokers
    
    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT = "http://otel-collector:4317"
    OTEL_EXPORTER_OTLP_INSECURE = "true"
    
    # Logging
    LOG_LEVEL = var.log_level
    LOG_FORMAT = "json"
  }
  
  tags = local.common_tags
}

# CloudWatch Module for monitoring
module "monitoring" {
  source = "./modules/monitoring"
  
  name_prefix = local.name_prefix
  
  # ECS cluster for monitoring
  ecs_cluster_name = module.ecs.cluster_name
  
  tags = local.common_tags
}

# IAM Module
module "iam" {
  source = "./modules/iam"
  
  name_prefix = local.name_prefix
  
  tags = local.common_tags
}
