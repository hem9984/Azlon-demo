FROM python:3.10-slim

WORKDIR /app
COPY pyproject.toml poetry.lock* /app/

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry && poetry install --no-root

COPY . /app

# FROM python:3.10-slim

# WORKDIR /app
# COPY pyproject.toml poetry.lock* /app/

# RUN apt-get update && apt-get install -y \
#     ca-certificates \
#     curl \
#     gnupg \
#     && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
#     && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
#     && apt-get update \
#     && apt-get install -y docker-buildx-plugin docker-compose-plugin \
#     && rm -rf /var/lib/apt/lists/*

# RUN pip install poetry && poetry install --no-root

# COPY . /app
