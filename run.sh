#!/usr/bin/env bash
# Local run on Apple Silicon Mac. First run builds a venv (~5 GB) + downloads
# model weights from Hugging Face (~2-4 GB per model). Needs ~15 GB free disk.
set -e
cd "$(dirname "$0")"

PY="${PYTHON_BIN:-/opt/homebrew/opt/python@3.13/bin/python3.13}"
[ -x "$PY" ] || PY="$(command -v python3.13 || command -v python3)"

if [ ! -d .venv ]; then
  echo ">> Creating venv with: $PY"
  "$PY" -m venv .venv
  ./.venv/bin/pip install -U pip wheel
  echo ">> Installing deps (torch/torchaudio here are the arm64 MPS builds)"
  ./.venv/bin/pip install -r requirements.txt
fi

# Some TTS ops have no MPS kernel yet -> silently fall back to CPU instead of crashing
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false
# leave GRADIO_SHARE unset -> opens http://127.0.0.1:7860 locally, no public link
exec ./.venv/bin/python app.py
