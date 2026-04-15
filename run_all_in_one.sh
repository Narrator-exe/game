#!/usr/bin/env bash
set -euo pipefail

MODEL="${OLLAMA_MODEL:-tinyllama:1.1b}"
export OLLAMA_MODEL="$MODEL"
export SIM_TICK_SECONDS="${SIM_TICK_SECONDS:-8}"
export MAX_MEMORIES="${MAX_MEMORIES:-48}"

echo "Starting lightweight stack for laptop use (model: $MODEL, tick: $SIM_TICK_SECONDS, max memories: $MAX_MEMORIES)"
docker compose up --build
