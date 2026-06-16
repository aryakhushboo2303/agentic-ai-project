#!/usr/bin/env bash
set -euo pipefail

echo "Starting infrastructure..."
docker compose up -d postgres chroma

echo "Waiting for services..."
sleep 5

echo "Done! Set GOOGLE_API_KEY in .env, then run: uvicorn app.main:app --reload"
