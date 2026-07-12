#!/bin/bash
# Gera arquivos de teste em tests/samples/ (DOCX, PDF, XLSX).
cd "$(dirname "$0")/.."
.venv/bin/python -m tests.make_samples
