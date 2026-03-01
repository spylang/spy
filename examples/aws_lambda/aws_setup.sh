#!/usr/bin/env bash
# One-shot setup: IAM role + Lambda function + public Function URL.
# Run this once. For subsequent deploys use aws_push.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_config.sh"

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { echo "  $*"; }
ok()    { echo "✓ $*"; }
warn()  { echo "! $*"; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# ── IAM role ───────────────────────────────────────────────────────────────────
echo
echo "==> IAM role"
if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
    warn "Role '$ROLE_NAME' already exists — skipping creation"
else
    info "Creating role '$ROLE_NAME'..."
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document '{
          "Version": "2012-10-17",
          "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
          }]
        }' \
        --output text --query 'Role.Arn' > /dev/null
    ok "Created role '$ROLE_NAME'"

    info "Attaching basic execution policy..."
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    ok "Policy attached"

    # IAM changes are eventually consistent; Lambda will reject the role if we
    # try to use it immediately.
    info "Waiting 15 s for IAM to propagate..."
    sleep 15
fi

# ── compile & package ─────────────────────────────────────────────────────────
echo
echo "==> Compiling & packaging"
bash "$SCRIPT_DIR/aws_push.sh" --package-only

# ── Lambda function ────────────────────────────────────────────────────────────
echo
echo "==> Lambda function"
if aws lambda get-function --function-name "$FUNCTION_NAME" \
       --region "$REGION" &>/dev/null; then
    warn "Function '$FUNCTION_NAME' already exists — skipping creation"
    info "Pushing code update instead..."
    bash "$SCRIPT_DIR/aws_push.sh" --deploy-only
else
    info "Creating function '$FUNCTION_NAME'..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --architectures "$ARCHITECTURE" \
        --role "$ROLE_ARN" \
        --handler bootstrap \
        --zip-file fileb://"$SCRIPT_DIR/function.zip" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --region "$REGION" \
        --output text --query 'FunctionArn' > /dev/null
    ok "Created function '$FUNCTION_NAME'"
fi

# ── Function URL (public HTTPS endpoint) ──────────────────────────────────────
echo
echo "==> Function URL"
if aws lambda get-function-url-config --function-name "$FUNCTION_NAME" \
       --region "$REGION" &>/dev/null; then
    warn "Function URL already exists — skipping creation"
else
    info "Creating Function URL..."
    aws lambda create-function-url-config \
        --function-name "$FUNCTION_NAME" \
        --auth-type NONE \
        --cors '{"AllowHeaders":["content-type"],"AllowMethods":["*"],"AllowOrigins":["*"],"MaxAge":86400}' \
        --region "$REGION" \
        --output text --query 'FunctionUrl' > /dev/null
    ok "Function URL created"
fi

# Always ensure both permissions are present. add-permission is not idempotent
# (duplicate statement IDs fail), so remove each before re-adding.
info "Ensuring public invoke permissions..."
for sid in FunctionURLAllowPublicInvoke FunctionURLAllowPublicAccess; do
    aws lambda remove-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "$sid" \
        --region "$REGION" &>/dev/null || true
done
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id FunctionURLAllowPublicInvoke \
    --action lambda:InvokeFunction \
    --principal "*" \
    --region "$REGION" \
    --output text --query 'Statement' > /dev/null
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    --region "$REGION" \
    --output text --query 'Statement' > /dev/null
ok "Public invoke permissions set"

# ── print URL ─────────────────────────────────────────────────────────────────
echo
URL=$(aws lambda get-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query FunctionUrl --output text)
echo "✓ Setup complete!"
echo
echo "  URL: $URL"
echo
