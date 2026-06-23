#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# If the package is not installed, add src/ to PYTHONPATH so it can be imported
if ! "$PYTHON" -c "import telemcp" 2>/dev/null; then
    export PYTHONPATH="$DIR/src${PYTHONPATH:+:$PYTHONPATH}"
fi

exec "$PYTHON" -m telemcp "$@"
