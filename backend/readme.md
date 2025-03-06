# Azlon Backend

## Overview

Azlon is a backend system for code generation, validation, and execution. It uses E2B sandboxes for secure code execution and MinIO for file storage. The backend handles code file uploads, code validation, and execution in isolated sandboxes.

## Architecture

The Azlon backend consists of the following key components:

### 1. E2B Sandbox Integration (`e2b_functions.py`)

The `E2BRunner` class provides an interface to interact with E2B sandboxes. Key functionalities include:

- Initializing a sandbox environment
- Installing packages in the sandbox
- Uploading and downloading files to/from the sandbox
- Running commands in the sandbox
- Generating directory trees for visualization

### 2. File Handling (`file_handling.py`)

The `PreFlightManager` class handles file operations, including:

- Collecting input files from local or remote sources
- Uploading files to MinIO storage
- Downloading files from MinIO storage
- Tracking file dependencies
- Generating directory trees of files

### 3. File Server (`file_server.py`)

Provides low-level operations for interacting with MinIO/S3 storage:

- Creating buckets
- Uploading files (from path or buffer)
- Downloading files (to path or as bytes)
- Listing files
- Deleting files
- Generating directory trees

### 4. Functions (`functions.py`)

Implements the core business logic of the system, including:

- Code validation and execution
- Workflow orchestration
- Processing inputs and outputs

## Environment Requirements

### Required Environment Variables

- `E2B_API_KEY`: Authentication key for E2B sandbox services
- `MINIO_ENDPOINT`: Endpoint URL for MinIO services
- `MINIO_ROOT_USER`: MinIO user for authentication
- `MINIO_ROOT_PASSWORD`: MinIO password for authentication
- `MINIO_USE_SSL`: Whether to use SSL for MinIO connections (true/false)

## Getting Started

### Installation

```bash
# Install dependencies using Poetry
make install
```

## Available Makefile Commands

The project includes a comprehensive Makefile that simplifies common development tasks:

| Command | Description |
|---------|-------------|
| `make help` | Show available commands |
| `make install` | Install all dependencies |
| `make test` | Run all tests |
| `make test-e2b` | Run only E2B function tests |
| `make test-file-handling` | Run only file handling tests |
| `make test-file-server` | Run only file server tests |
| `make test-coverage` | Run tests with coverage report |
| `make lint` | Run linting checks |
| `make format` | Format code with Black and isort |
| `make clean` | Remove __pycache__, .pytest_cache, etc. |
| `make cleanup` | Format and clean code |
| `make check` | Run linting and tests |
| `make start-server` | Build and start Docker containers with Tailscale |
| `make all` | Install, format, lint, and test |

## Workflow Execution

To run the backend system:

### 1. Start the Server

```bash
# Build and start Docker containers with Tailscale
make start-server
```

This command:
- Builds and starts Docker containers in detached mode
- Configures Tailscale Funnel to expose services publicly
- Maps local ports to public endpoints:
  - Backend on port 8000 -> https://muchnic.tail9dec88.ts.net/ (port 443)
  - MinIO on port 9000 -> https://muchnic.tail9dec88.ts.net:8443/ (port 8443)

### 2. Run a Workflow

```bash
# Simulate a request from the frontend
poetry run schedule
```

This command schedules a workflow to execute immediately, emulating a request from the frontend.

## Testing

```bash
# Run all tests
make test

# Run tests with coverage report
make test-coverage
```

## Development Workflow

1. Make code changes
2. Format code: `make format`
3. Run tests: `make test`
4. Run linting: `make lint`
5. Start the server: `make start-server`
6. Simulate a frontend request: `poetry run schedule`

## Docker Management

```bash
# Reset Docker cache for development purposes
docker compose down -v
docker compose up --build
```

## Restack Integration

Restack is used for workflow orchestration:

```bash
# Start Restack engine
docker run -d --pull always --name restack -p 5233:5233 -p 6233:6233 -p 7233:7233 ghcr.io/restackio/restack:main

# Stop Restack container
docker kill restack

# Remove stopped Restack container
docker rm restack
```

Visit the Developer UI to see executed workflows: http://localhost:5233

## Important Implementation Notes

1. The backend uses synchronous (non-async) methods for simplicity and compatibility
2. File operations are designed to handle both local files and remote sources
3. Error handling is implemented throughout the codebase for robustness
4. Type hints are used for better IDE support and code quality
5. The system uses isolated sandboxes for secure code execution
