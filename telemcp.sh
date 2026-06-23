#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

exec "$PYTHON" "$DIR/server.py" "$@"
