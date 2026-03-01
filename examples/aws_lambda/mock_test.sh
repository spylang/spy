#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=9001

python "$SCRIPT_DIR/mock_runtime.py" $PORT &
MOCK_PID=$!
sleep 0.3

AWS_LAMBDA_RUNTIME_API=127.0.0.1:$PORT "$SCRIPT_DIR/build/hello" 2>/dev/null &
HELLO_PID=$!

# The mock exits with 0 on success, 1 on timeout — use that as the test result.
wait $MOCK_PID
RESULT=$?

kill $HELLO_PID 2>/dev/null || true
wait $HELLO_PID 2>/dev/null || true

exit $RESULT
