#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

if ! pgrep redis-server > /dev/null; then
  echo "Starting local Redis..."
  redis-server --save '' --appendonly no >/dev/null 2>&1 &
fi

if [ -z "$REDIS_URL" ]; then
  echo "REDIS_URL not set; defaulting to redis://localhost:6379/0"
  export REDIS_URL="redis://localhost:6379/0"
fi

echo "Starting ClassPulse..."
python -m ClassPulse.app