#!/usr/bin/env bash
# SET-QuantAI CLI Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
"$DIR/.venv/bin/python" -m set_quantai.cli "$@"
