#!/bin/sh
set -e

echo "Starting the Restack engine in the background..."
docker-entrypoint.sh pnpm start &

sleep 3

echo "Starting socat sidecar from 0.0.0.0:443 -> 127.0.0.1:7233 (Temporal)..."
socat TCP-LISTEN:443,fork,reuseaddr TCP:127.0.0.1:7233 &

echo "Starting second socat sidecar on 0.0.0.0:65433 -> 127.0.0.1:6233..."
socat TCP-LISTEN:65433,fork,reuseaddr TCP:127.0.0.1:6233 &

wait
