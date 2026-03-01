#!/bin/bash
set -e

FUNCTION_NAME="hello-c-lambda"
REGION="${AWS_REGION:-us-east-1}"

echo "Packaging..."
cp build/hello bootstrap
zip -j function.zip bootstrap

echo "Uploading to Lambda..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://function.zip \
    --region "$REGION"

echo "Cleaning up..."
rm -f bootstrap function.zip

echo "Lambda function updated successfully!"
