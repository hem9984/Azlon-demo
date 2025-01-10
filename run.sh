#!/bin/sh
set -e

echo "Starting the Restack engine..."
docker-entrypoint.sh pnpm start &

sleep 3

echo "Starting socat sidecar from 0.0.0.0:443 -> localhost:7233..."
socat TCP-LISTEN:443,fork,reuseaddr TCP:127.0.0.1:7233 &

wait
