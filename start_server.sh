#!/usr/bin/env bash
set -e

##############################################################################
# 1) Build & Start Docker Containers
##############################################################################
echo "=== Building and starting Docker containers (detached) ==="
sudo docker compose up --build -d

echo "=== Waiting a few seconds for containers to come online ==="
sleep 3

##############################################################################
# 2) Reset Tailscale Funnel Config (Optional)
##############################################################################
# This wipes any previous funnel mappings so we start clean.
echo "=== Resetting Tailscale Funnel configuration ==="
sudo tailscale funnel reset || true

##############################################################################
# 3) Expose backend via Funnel on Port 443
##############################################################################
# This means https://<machine-name>.ts.net/ will map to local port 8000 (backend).
echo "=== Enabling Funnel for local port 8000 -> public port 443 ==="
sudo tailscale funnel --bg --https=443 8000

##############################################################################
# 4) Expose Minio (S3 compatible) via Funnel on Port 8443
##############################################################################
# This means https://<machine-name>.ts.net:8443/ will map to local port 9000 (minio).
echo "=== Enabling Funnel for local port 9000 -> public port 8443 ==="
sudo tailscale funnel --bg --https=8443 9000

##############################################################################
# 5) Show Final Status
##############################################################################
echo
echo "=== Tailscale Funnel Status ==="
tailscale funnel status || true

echo
echo "==============================================================="
echo "DONE! Your services should be mapped as follows:"
echo "1) Backend on port 8000 -> https://muchnic.tail9dec88.ts.net/       (port 443)"
echo "2) Minio (S3 compatible) on port 9000 -> https://muchnic.tail9dec88.ts.net:8443/  (port 8443)"
echo
echo "If you see '(tailnet only)' in the status, ensure you have the 'funnel'"
echo "attribute in your tailnet policy file or have accepted the funnel consent."
echo "==============================================================="


# This way, any requests to https://<machine>.ts.net/ go to your backend (port 8000).
# Requests to https://<machine>.ts.net:8443/ go to MinIO (port 9000).