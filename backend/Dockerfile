#./backend/Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* /app/

# Install dependencies and Docker CLI tools
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-buildx-plugin docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry && poetry install --no-root

# Create and ensure permissions for output directory
RUN mkdir -p /app/output && chmod 777 /app/output

# Copy application files
COPY . /app

# Expose application port
EXPOSE 8000