.PHONY: help build up down logs test test-unit test-integration test-load clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d
	@echo "Services starting..."
	@echo "Gateway: http://localhost:8000"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Jaeger: http://localhost:16686"

down: ## Stop all services
	docker-compose down

logs: ## View logs from all services
	docker-compose logs -f

logs-service: ## View logs from specific service (usage: make logs-service SERVICE=gateway)
	docker-compose logs -f $(SERVICE)

test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests
	docker-compose exec gateway python -m pytest tests/unit/ -v
	docker-compose exec shortener python -m pytest tests/unit/ -v
	docker-compose exec redirector python -m pytest tests/unit/ -v
	docker-compose exec analytics python -m pytest tests/unit/ -v

test-integration: ## Run integration tests
	docker-compose exec gateway python -m pytest tests/integration/ -v

test-load: ## Run load tests
	docker run --rm -i grafana/k6 run - < tests/load/load_test.js

clean: ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f

dev-setup: ## Setup development environment
	python -m venv venv
	source venv/bin/activate && pip install -r requirements-dev.txt

lint: ## Run linting
	docker-compose exec gateway python -m flake8 app/
	docker-compose exec shortener python -m flake8 app/
	docker-compose exec redirector python -m flake8 app/
	docker-compose exec analytics python -m flake8 app/

format: ## Format code
	docker-compose exec gateway python -m black app/
	docker-compose exec shortener python -m black app/
	docker-compose exec redirector python -m black app/
	docker-compose exec analytics python -m black app/

shell-gateway: ## Open shell in gateway service
	docker-compose exec gateway bash

shell-shortener: ## Open shell in shortener service
	docker-compose exec shortener bash

shell-redirector: ## Open shell in redirector service
	docker-compose exec redirector bash

shell-analytics: ## Open shell in analytics service
	docker-compose exec analytics bash

migrate: ## Run database migrations
	docker-compose exec shortener python -m alembic upgrade head
	docker-compose exec analytics python -m alembic upgrade head

seed: ## Seed database with test data
	docker-compose exec shortener python scripts/seed_data.py
