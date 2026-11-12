#!/usr/bin/env bash
# Install once as /opt/cne/deploy-release.sh on the deployment host.
set -euo pipefail
cd /opt/cne
test -f .env
test -f incoming.tar.gz
stamp=$(date -u +%Y%m%d%H%M%S)-$$
release="/opt/cne/releases/$stamp"
mkdir -p "$release"
tar -xzf incoming.tar.gz -C "$release"
ln -s /opt/cne/.env "$release/.env"
cd "$release"
# Project name is stable across release directories: preserve database volumes.
docker compose -p cne -f compose.production.yaml build
# Run one schema migration before rolling the API and workers forward.
docker compose -p cne -f compose.production.yaml up -d db redis
docker compose -p cne -f compose.production.yaml run --rm migrate
docker compose -p cne -f compose.production.yaml up -d --remove-orphans
ln -sfn "$release" /opt/cne/current
printf 'Release deployed: %s\n' "$stamp"
