#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${1:-cleaned_data}"
INDEX_NAME="${2:-bluesky_posts}"

python indexer.py "$INPUT_DIR" "$INDEX_NAME"
