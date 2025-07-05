# URL Shortener Platform

A production-ready, distributed URL shortening platform built with Python (FastAPI), Docker, Redis, PostgreSQL, Kafka, and full observability stack.

## 🏗️ Architecture

### Microservices
- **Gateway Service** (`services/gateway/`) - API Gateway with rate limiting and routing
- **Shortener Service** (`services/shortener/`) - URL shortening with base62 encoding
- **Redirector Service** (`services/redirector/`) - URL resolution and click tracking
- **Analytics Service** (`services/analytics/`) - Event processing and analytics

### Infrastructure
- **PostgreSQL** - Primary data store
- **Redis** - Caching layer
- **Kafka** - Event streaming
- **OpenTelemetry** - Distributed tracing and metrics
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards and visualization
- **Loki** - Log aggregation

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Make

### Local Development
```bash
# Start all services
make up

# View logs
make logs

# Run tests
make test

# Stop services
make down
```

### API Endpoints
- `POST /api/v1/shorten` - Create short URL
- `GET /<code>` - Redirect to original URL
- `GET /api/v1/analytics/<code>` - Get URL analytics

## 📊 Observability

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686

## 🏗️ Infrastructure

### AWS Deployment
```bash
cd infra/
terraform init
terraform plan
terraform apply
```

## 📝 Development

### Service Structure
Each service follows the same pattern:
- FastAPI application
- OpenTelemetry instrumentation
- Health checks
- Structured logging
- Docker containerization

### Environment Variables
See `.env.example` for required configuration.

## 🧪 Testing

```bash
# Unit tests
make test-unit

# Integration tests
make test-integration

# Load tests
make test-load
```

## 📚 Documentation

- [API Documentation](docs/api.md)
- [Deployment Guide](docs/deployment.md)
- [Monitoring Guide](docs/monitoring.md)
