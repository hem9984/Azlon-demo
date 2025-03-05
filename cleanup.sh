#!/bin/bash

# Script to run code cleanup and formatting tasks

# Change to the backend directory
cd "$(dirname "$0")/backend"

# Run the format command from the Makefile
poetry run autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive src tests
poetry run black src tests
poetry run isort src tests

echo "✅ Code cleanup completed!"
