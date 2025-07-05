# General variables
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "url-shortener"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

# VPC variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Database variables
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "urlshortener"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Redis variables
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

# Kafka variables
variable "kafka_version" {
  description = "Kafka version"
  type        = string
  default     = "2.8.1"
}

variable "kafka_instance_type" {
  description = "Kafka instance type"
  type        = string
  default     = "kafka.t3.small"
}

variable "kafka_number_of_nodes" {
  description = "Number of Kafka nodes"
  type        = number
  default     = 2
}

# Container images
variable "gateway_image" {
  description = "Gateway service container image"
  type        = string
  default     = "ghcr.io/your-org/url-shortener-gateway:latest"
}

variable "shortener_image" {
  description = "Shortener service container image"
  type        = string
  default     = "ghcr.io/your-org/url-shortener-shortener:latest"
}

variable "redirector_image" {
  description = "Redirector service container image"
  type        = string
  default     = "ghcr.io/your-org/url-shortener-redirector:latest"
}

variable "analytics_image" {
  description = "Analytics service container image"
  type        = string
  default     = "ghcr.io/your-org/url-shortener-analytics:latest"
}

# Application variables
variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
  default     = ""
}

# Monitoring variables
variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "retention_days" {
  description = "CloudWatch logs retention in days"
  type        = number
  default     = 7
}

# Auto scaling variables
variable "min_capacity" {
  description = "Minimum number of tasks"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of tasks"
  type        = number
  default     = 10
}

variable "target_cpu_utilization" {
  description = "Target CPU utilization for auto scaling"
  type        = number
  default     = 70
}

variable "target_memory_utilization" {
  description = "Target memory utilization for auto scaling"
  type        = number
  default     = 80
}
