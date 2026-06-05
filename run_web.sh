#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=web.app
export FLASK_RUN_HOST="${FLASK_RUN_HOST:-0.0.0.0}"
export FLASK_RUN_PORT="${FLASK_RUN_PORT:-5000}"

flask run
