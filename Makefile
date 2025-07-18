.PHONY: help install dev-install test test-unit test-integration lint format type-check security clean build docker-build docker-run docs serve-docs

# Default target
help:
	@echo "Available commands:"
	@echo "  make install         Install the package"
	@echo "  make dev-install     Install with development dependencies"
	@echo "  make test           Run all tests with coverage"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make lint           Run all linters"
	@echo "  make format         Format code with black"
	@echo "  make type-check     Run type checking with mypy"
	@echo "  make security       Run security checks"
	@echo "  make clean          Clean build artifacts"
	@echo "  make build          Build distribution packages"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo "  make docs           Build documentation"
	@echo "  make serve-docs     Serve documentation locally"

# Installation
install:
	pip install -e .

dev-install:
	pip install -e ".[dev,test,docs]"
	pre-commit install

# Testing
test:
	pytest --cov=otel_query_server --cov-report=html --cov-report=term --cov-report=xml -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-watch:
	ptw tests/ -- -v

# Code Quality
lint: format type-check ruff-check security

format:
	black src tests

format-check:
	black --check src tests

ruff-check:
	ruff check src tests

ruff-fix:
	ruff check --fix src tests

type-check:
	mypy src

security:
	bandit -r src/
	pip-audit

# Cleaning
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Building
build: clean
	python -m build

# Docker
docker-build:
	docker build -t otel-query-server:latest .

docker-run:
	docker run --rm -it \
		-v $(PWD)/config.yaml:/app/config.yaml \
		-p 8080:8080 \
		otel-query-server:latest

docker-compose-up:
	docker-compose -f examples/docker-compose.yaml up -d

docker-compose-down:
	docker-compose -f examples/docker-compose.yaml down

docker-compose-logs:
	docker-compose -f examples/docker-compose.yaml logs -f

# Documentation
docs:
	mkdocs build

serve-docs:
	mkdocs serve

# Development server
run:
	python -m otel_query_server.server --config config.yaml

run-debug:
	OTEL_QUERY_SERVER__LOG_LEVEL=DEBUG python -m otel_query_server.server --config config.yaml

# MCP specific
mcp-run:
	fastmcp run otel_query_server.server:mcp

mcp-run-http:
	fastmcp run otel_query_server.server:mcp --transport http --port 8080

# CI simulation
ci: clean lint test build

# Quick checks before committing
pre-commit: format lint test-unit 