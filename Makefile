# ============================================
# SentinelAI - Makefile
# ============================================
# Common commands for development and deployment
# ============================================

.PHONY: help install dev test lint format run docker-build docker-up docker-down clean

# Default target
help:
	@echo "SentinelAI - Available Commands"
	@echo "================================"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo "  make test         Run test suite"
	@echo "  make lint         Run linters"
	@echo "  make format       Format code"
	@echo "  make run          Run the API server"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-up    Start Docker Compose stack"
	@echo "  make docker-down  Stop Docker Compose stack"
	@echo "  make clean        Clean build artifacts"

# Install production dependencies
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"
	pre-commit install

# Run tests
test:
	pytest tests/ -v --cov=sentinelai --cov-report=term-missing

# Run tests with HTML coverage report
test-cov:
	pytest tests/ -v --cov=sentinelai --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Run linters
lint:
	ruff check sentinelai tests
	mypy sentinelai

# Format code
format:
	black sentinelai tests
	ruff check --fix sentinelai tests

# Run the API server
run:
	python -m sentinelai.cli serve

# Run with reload for development
run-dev:
	python -m sentinelai.cli serve --reload

# Run analysis on sample cases
analyze:
	python -m sentinelai.cli analyze sample_cases.json -o results.json

# Build Docker image
docker-build:
	docker build -t sentinelai:latest .

# Start Docker Compose stack
docker-up:
	docker-compose up -d

# Start with monitoring
docker-up-full:
	docker-compose --profile monitoring up -d

# Stop Docker Compose stack
docker-down:
	docker-compose down

# View Docker logs
docker-logs:
	docker-compose logs -f sentinelai

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Generate requirements.txt from pyproject.toml
requirements:
	pip-compile pyproject.toml -o requirements.txt
	pip-compile pyproject.toml --extra dev -o requirements-dev.txt

# Database migrations (when using Alembic)
db-init:
	alembic init alembic

db-migrate:
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

# Generate API documentation
docs:
	@echo "API documentation available at http://localhost:8000/docs"
	@echo "ReDoc available at http://localhost:8000/redoc"
