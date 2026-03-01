#!/bin/bash

# Script to get the URL associated with an AWS Lambda function
FUNCTION_NAME="antocuni-hello-world"

echo "Getting URL for Lambda function: $FUNCTION_NAME"
echo ""

# Try to get the Function URL (if configured)
FUNCTION_URL=$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --query 'FunctionUrl' --output text 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$FUNCTION_URL" ] && [ "$FUNCTION_URL" != "None" ]; then
    echo "Function URL:"
    echo "$FUNCTION_URL"
else
    echo "No Function URL configured for this Lambda."
    echo ""
    echo "To create a Function URL, run:"
    echo "  aws lambda create-function-url-config --function-name $FUNCTION_NAME --auth-type AWS_IAM"
    echo "or"
    echo "  aws lambda create-function-url-config --function-name $FUNCTION_NAME --auth-type NONE"
    echo ""

    # Get the function ARN as alternative info
    FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.FunctionArn' --output text 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "Function ARN:"
        echo "$FUNCTION_ARN"
    fi
fi
