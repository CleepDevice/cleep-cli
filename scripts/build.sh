#!/bin/bash
set -eu
cd "$(dirname "$0")/.."
rm -rf dist/ build/ *.egg-info
python3 -m pip install -q --upgrade build
python3 -m build
ls -la dist/
