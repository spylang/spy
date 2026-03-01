#!/usr/bin/env bash
# Delete the Lambda function and its Function URL.
# The IAM role is shared and NOT deleted here — remove it manually if unused.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_config.sh"

warn() { echo "! $*"; }
ok()   { echo "✓ $*"; }

echo
echo "==> Tearing down '$FUNCTION_NAME' (region: $REGION)"
echo

read -r -p "  Are you sure? This cannot be undone. [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
echo

if aws lambda get-function-url-config --function-name "$FUNCTION_NAME" \
       --region "$REGION" &>/dev/null; then
    echo "  Deleting Function URL..."
    aws lambda delete-function-url-config \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
    ok "Function URL deleted"
else
    warn "No Function URL found — skipping"
fi

if aws lambda get-function --function-name "$FUNCTION_NAME" \
       --region "$REGION" &>/dev/null; then
    echo "  Deleting Lambda function..."
    aws lambda delete-function \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
    ok "Function deleted"
else
    warn "Function '$FUNCTION_NAME' not found — skipping"
fi

echo
echo "✓ Done."
echo
echo "  Note: IAM role '$ROLE_NAME' was NOT deleted (it may be shared)."
echo "  To delete it manually:"
echo "    aws iam detach-role-policy --role-name $ROLE_NAME \\"
echo "      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
echo "    aws iam delete-role --role-name $ROLE_NAME"
echo
