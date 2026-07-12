#!/bin/bash
# Atalho opcional — o executor principal é run_desktop.py
cd "$(dirname "$0")"
exec .venv/bin/python run_desktop.py "$@"
