.PHONY: help install test test-all test-e2b test-file-handling test-file-server test-coverage lint format clean cleanup check all start-server stop-server

help:
	@echo "Available commands:"
	@echo "  make install           Install all dependencies"
	@echo "  make test              Run all tests"
	@echo "  make test-e2b          Run only E2B function tests"
	@echo "  make test-file-handling Run only file handling tests"
	@echo "  make test-file-server  Run only file server tests"
	@echo "  make test-coverage     Run tests with coverage report"
	@echo "  make lint              Run linting checks"
	@echo "  make format            Format code"
	@echo "  make clean             Remove __pycache__, .pytest_cache, etc."
	@echo "  make cleanup           Format and clean code (same as cleanup.sh)"
	@echo "  make check             Run linting and tests"
	@echo "  make start-server      Build and start Docker containers with Tailscale"
	@echo "  make stop-server       Stop Docker containers and cleanup networks"
	@echo "  make all               Install, format, lint, and test"

install:
	@echo "Installing dependencies..."
	poetry install

test: test-all

test-all:
	@echo "Running all tests..."
	poetry run pytest -xvs tests/

test-e2b:
	@echo "Running E2B function tests..."
	poetry run pytest -xvs tests/test_e2b_functions.py

test-file-handling:
	@echo "Running file handling tests..."
	poetry run pytest -xvs tests/test_file_handling.py

test-file-server:
	@echo "Running file server tests..."
	poetry run pytest -xvs tests/test_file_server.py

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

cleanup: format
	@echo "✅ Code cleanup completed!"

start-server:
	@echo "=== Building and starting Docker containers (detached) ==="
	sudo docker compose up --build -d
	@echo "=== Waiting a few seconds for containers to come online ==="
	sleep 3
	@echo "=== Resetting Tailscale Funnel configuration ==="
	sudo tailscale funnel reset || true
	@echo "=== Enabling Funnel for local port 8000 -> public port 443 ==="
	sudo tailscale funnel --bg --https=443 8000
	@echo "=== Enabling Funnel for local port 9000 -> public port 8443 ==="
	sudo tailscale funnel --bg --https=8443 9000
	@echo "\n=== Tailscale Funnel Status ==="
	tailscale funnel status || true
	@echo "\n==============================================================="
	@echo "DONE! Your services should be mapped as follows:"
	@echo "1) Backend on port 8000 -> https://muchnic.tail9dec88.ts.net/       (port 443)"
	@echo "2) Minio (S3 compatible) on port 9000 -> https://muchnic.tail9dec88.ts.net:8443/  (port 8443)"
	@echo "\nIf you see '(tailnet only)' in the status, ensure you have the 'funnel'"
	@echo "attribute in your tailnet policy file or have accepted the funnel consent."
	@echo "==============================================================="

check: lint test-all

stop-server:
	@echo "=== Stopping Tailscale Funnel services ==="
	sudo tailscale funnel reset || true
	@echo "=== Stopping Docker containers and removing networks ==="
	cd .. && sudo docker compose down --remove-orphans || true
	@echo "=== Forcefully removing any dangling networks (if any) ==="
	sudo docker network prune -f || true
	@echo "\n=== Services successfully stopped ==="

all: install format lint test-all
