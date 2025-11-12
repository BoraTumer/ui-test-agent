#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python -m playwright install --with-deps chromium
python -m ui_test_agent run --scenario scenarios/login.yml --config config.yaml "$@"
