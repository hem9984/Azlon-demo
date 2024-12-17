FROM python:3.10-slim

WORKDIR /app
COPY pyproject.toml poetry.lock* /app/

RUN apt-get update && apt-get install -y docker-cli && rm -rf /var/lib/apt/lists/*

RUN pip install poetry && poetry install --no-root

COPY . /app
