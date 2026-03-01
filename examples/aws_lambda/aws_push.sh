#!/usr/bin/env bash
# Compile demo.spy, package the binary, and deploy to Lambda.
# Flags (used internally by aws_setup.sh):
#   --package-only   build function.zip but don't push
#   --deploy-only    push existing function.zip without recompiling
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_config.sh"

# Resolve the SPy venv relative to the repo root (two levels up from examples/aws_lambda/).
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPY="$REPO_ROOT/venv/bin/spy"

PACKAGE_ONLY=false
DEPLOY_ONLY=false
for arg in "$@"; do
    case $arg in
        --package-only) PACKAGE_ONLY=true ;;
        --deploy-only)  DEPLOY_ONLY=true ;;
    esac
done

# ── compile ───────────────────────────────────────────────────────────────────
if ! $DEPLOY_ONLY; then
    echo "==> Compiling"

    echo "  Running spy build demo.spy..."
    cd "$SCRIPT_DIR"
    "$SPY" build --static --release demo.spy

    echo "  Packaging..."
    cp build/demo "$SCRIPT_DIR/bootstrap"
    (cd "$SCRIPT_DIR" && zip -q -j function.zip bootstrap)
    rm -f "$SCRIPT_DIR/bootstrap"

    SIZE=$(du -sh "$SCRIPT_DIR/function.zip" | cut -f1)
    echo "✓ function.zip ready ($SIZE)"
fi

$PACKAGE_ONLY && exit 0

# ── deploy ────────────────────────────────────────────────────────────────────
echo
echo "==> Deploying"

if ! aws lambda get-function --function-name "$FUNCTION_NAME" \
        --region "$REGION" &>/dev/null; then
    echo "Error: function '$FUNCTION_NAME' does not exist." >&2
    echo "Run aws_setup.sh first." >&2
    exit 1
fi

echo "  Uploading function.zip..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://"$SCRIPT_DIR/function.zip" \
    --region "$REGION" \
    --output text --query 'CodeSize' > /dev/null

echo "  Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

URL=$(aws lambda get-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query FunctionUrl --output text 2>/dev/null || echo "(no Function URL configured)")

echo
echo "✓ Deploy complete!"
echo
echo "  URL: $URL"
echo
