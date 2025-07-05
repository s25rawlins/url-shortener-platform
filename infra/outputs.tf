# VPC outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

# Database outputs
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.rds.port
}

# Redis outputs
output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.redis_endpoint
  sensitive   = true
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = module.elasticache.redis_port
}

# Kafka outputs
output "kafka_bootstrap_brokers" {
  description = "Kafka bootstrap brokers"
  value       = module.msk.bootstrap_brokers
  sensitive   = true
}

output "kafka_zookeeper_connect" {
  description = "Kafka Zookeeper connection string"
  value       = module.msk.zookeeper_connect
  sensitive   = true
}

# ECS outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.ecs.cluster_arn
}

output "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  value       = module.ecs.load_balancer_dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  value       = module.ecs.load_balancer_zone_id
}

# Service URLs
output "gateway_url" {
  description = "URL of the gateway service"
  value       = "http://${module.ecs.load_balancer_dns_name}"
}

output "api_url" {
  description = "API URL for the application"
  value       = "http://${module.ecs.load_balancer_dns_name}/api/v1"
}

# Security Group outputs
output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = module.security_groups.alb_security_group_id
}

output "ecs_security_group_id" {
  description = "ID of the ECS security group"
  value       = module.security_groups.ecs_security_group_id
}

# Monitoring outputs
output "cloudwatch_log_group_names" {
  description = "Names of CloudWatch log groups"
  value       = module.monitoring.log_group_names
}

# IAM outputs
output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.iam.ecs_task_role_arn
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  value       = module.iam.ecs_execution_role_arn
}
