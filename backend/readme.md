# Azlon Backend

## Overview

Azlon is a production-ready backend system for code generation, validation, and execution. It leverages Restack cloud for reliable workflow orchestration, E2B sandboxes for secure code execution, and MinIO for file storage. The system seamlessly handles code generation, validation, and execution in isolated environments, providing a robust platform for autonomous coding workflows.

## System Architecture

The Azlon backend consists of the following key components:

### 1. Restack Cloud Workflow Orchestration (`client.py`)

The system uses Restack AI's cloud service for reliable workflow orchestration:

- Handles workflow scheduling and execution in the cloud
- Manages user context and workflow state across activities
- Provides robust error handling and retry mechanisms
- Enables scalable execution of complex workflows

### 2. E2B Sandbox Integration (`e2b_functions.py`)

The `E2BRunner` class provides an interface to interact with E2B sandboxes for secure code execution:

- Initializes isolated sandbox environments
- Installs packages and dependencies
- Uploads and downloads files to/from the sandbox
- Executes commands in secure environments
- Generates directory trees for visualization

### 3. File Handling and Storage

#### File Handling (`file_handling.py`)

The `PreFlightManager` class handles file operations:

- Collects input files from local or remote sources
- Uploads files to MinIO storage
- Downloads files from MinIO storage
- Tracks file dependencies and relationships
- Generates directory trees for visualization

#### File Server (`file_server.py`)

Provides low-level operations for MinIO/S3 storage in both local and cloud environments:

- Creates and manages buckets with user isolation
- Handles file uploads (from path or buffer)
- Downloads files (to path or as bytes)
- Lists files with path filtering
- Deletes files and buckets

### 4. API Server (`main.py`)

The FastAPI server provides HTTP endpoints for frontend integration:

- Handles user authentication and tracking via header (`X-User-ID`)
- Schedules Restack workflows with user context
- Retrieves workflow results and file outputs
- Serves file content and metadata

### 5. Core Business Logic (`functions.py`)

Implements the domain-specific logic including:

- Code generation and validation
- Test execution and validation
- Input/output processing
- Error handling and reporting

## Workflow Process

1. **Request Initiation**: Frontend sends a request to `/run_workflow` with user prompt and test conditions
2. **User Identification**: System extracts user ID from request headers or payload
3. **Workflow Scheduling**: Backend schedules a workflow on Restack cloud with unique workflow ID
4. **File Management**: System manages file storage in MinIO with user-specific buckets
5. **Secure Execution**: Code runs in isolated E2B sandboxes for security
6. **Result Retrieval**: Results are stored in MinIO and made available to the frontend

## User ID Management

User identification is critical for proper resource isolation and tracking:

- User IDs come from Firebase authentication in production
- Each user has isolated storage buckets and workflow instances
- Workflow IDs follow the pattern: `user-{user_id}-{timestamp}`
- If no user ID is provided, the system uses "anonymous" as fallback

## Deployment Environments

### Local Development

```
USE_EXTERNAL_MINIO=false
```

In local development, the system uses internal Docker networking:
- MinIO endpoint: `minio:9000`
- Backend URL: `http://backend:8000`

### Cloud Production

```
USE_EXTERNAL_MINIO=true
MINIO_EXTERNAL_ENDPOINT=https://yourinstance.ts.net:8443
EXTERNAL_BACKEND_URL=https://yourinstance.ts.net
```

In cloud production, the system uses Tailscale for secure networking:
- Public MinIO endpoint for file access
- Public backend URL for API access
- Restack cloud for workflow processing

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

**Note on MinIO Configuration:**
- Internal container communication uses: `minio:9000` (Docker service name)
- External access URL: `https://muchnic.tail9dec88.ts.net:8443/`
- The backend service is configured to use the internal endpoint

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
