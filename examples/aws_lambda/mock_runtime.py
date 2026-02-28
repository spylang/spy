"""
Mock AWS Lambda Runtime API server for testing.

Serves a single invocation, waits for the handler's response, then exits.
"""
import http.server
import json
import sys
import threading


class MockLambdaRuntime(http.server.HTTPServer):
    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), MockHandler)
        self.invocation_response = None
        self.got_response = threading.Event()


class MockHandler(http.server.BaseHTTPRequestHandler):
    server: MockLambdaRuntime

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if "/invocation/next" in self.path:
            event = json.dumps({
                "body": "test-body-from-mock",
                "requestContext": {"http": {"method": "GET"}},
            })
            self.send_response(200)
            self.send_header("Lambda-Runtime-Aws-Request-Id", "test-request-123")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(event.encode())

    def do_POST(self):
        if "/invocation/test-request-123/response" in self.path:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            self.server.invocation_response = json.loads(body)
            self.send_response(202)
            self.end_headers()
            self.server.got_response.set()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    server = MockLambdaRuntime(port)
    print(f"Mock Lambda runtime on port {port}", flush=True)

    # Serve until we get a response from the handler
    def serve():
        while not server.got_response.is_set():
            server.handle_request()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    server.got_response.wait(timeout=10)

    if server.invocation_response:
        print(f"Got response: {json.dumps(server.invocation_response)}")
        status = server.invocation_response.get("statusCode", -1)
        resp_body = server.invocation_response.get("body", "")
        print(f"Status: {status}")
        print(f"Body: {resp_body}")
        sys.exit(0)
    else:
        print("Timed out waiting for response")
        sys.exit(1)


if __name__ == "__main__":
    main()
