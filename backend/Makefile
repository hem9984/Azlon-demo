.PHONY: help install test lint format clean check all

help:
	@echo "Available commands:"
	@echo "  make install      Install all dependencies"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linting checks"
	@echo "  make format       Format code"
	@echo "  make clean        Remove __pycache__, .pytest_cache, etc."
	@echo "  make check        Run linting and tests"
	@echo "  make all          Install, format, lint, and test"

install:
	@echo "Installing dependencies..."
	poetry install

test:
	@echo "Running tests..."
	poetry run pytest -xvs tests/

test-coverage:
	@echo "Running tests with coverage..."
	poetry run pytest --cov=src tests/ --cov-report=term-missing

lint:
	@echo "Linting code..."
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --recursive src tests
	poetry run black --check src tests
	poetry run isort --check-only src tests
	poetry run mypy src

format:
	@echo "Formatting code..."
	poetry run autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive src tests
	poetry run black src tests
	poetry run isort src tests

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +

check: lint test

all: install format lint test
