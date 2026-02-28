#ifndef AWS_LAMBDA_H
#define AWS_LAMBDA_H

// Handler function type: receives the HTTP request body as a string.
typedef void (*aws_lambda_handler_t)(const char *body);

// Start the Lambda runtime event loop.
// Fetches events from the AWS Lambda Runtime API, extracts the HTTP body
// from Function URL events, and calls handler for each request.
// Does not return under normal operation.
void aws_lambda_start(aws_lambda_handler_t handler);

// Send an HTTP response for the current Lambda invocation.
// Must be called exactly once from within the handler.
//   status_code: HTTP status code (e.g. 200, 400, 500)
//   body:        response body string (will be returned as-is to the caller)
void aws_response(int status_code, const char *body);

// Extract a JSON string field value from a JSON object string.
// Returns a malloc'd string that the caller must free(), or NULL if not found.
char *aws_json_extract(const char *json, const char *field);

#endif // AWS_LAMBDA_H
