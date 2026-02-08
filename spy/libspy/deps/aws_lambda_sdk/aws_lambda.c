#include "aws_lambda.h"

#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// --- Internal types and globals ---

typedef struct {
    char *data;
    size_t size;
} MemoryStruct;

static const char *g_runtime_api; // AWS_LAMBDA_RUNTIME_API value
static char g_request_id[256];    // current invocation request ID
static CURL *g_curl;              // reused curl handle

// --- Internal helpers ---

static size_t
write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    MemoryStruct *mem = (MemoryStruct *)userp;

    char *ptr = realloc(mem->data, mem->size + realsize + 1);
    if (!ptr) {
        fprintf(stderr, "aws_lambda: out of memory\n");
        return 0;
    }

    mem->data = ptr;
    memcpy(&mem->data[mem->size], contents, realsize);
    mem->size += realsize;
    mem->data[mem->size] = 0;

    return realsize;
}

static int
extract_request_id(const char *headers) {
    const char *key = "Lambda-Runtime-Aws-Request-Id:";
    char *start = strstr(headers, key);
    if (!start)
        return -1;

    start += strlen(key);
    while (*start == ' ')
        start++;

    char *end = strchr(start, '\r');
    if (!end)
        end = strchr(start, '\n');
    if (!end)
        return -1;

    size_t len = end - start;
    if (len >= sizeof(g_request_id))
        return -1;

    memcpy(g_request_id, start, len);
    g_request_id[len] = '\0';
    return 0;
}

// --- Public API ---

char *
aws_json_extract(const char *json, const char *field) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", field);

    char *field_start = strstr(json, search);
    if (!field_start)
        return NULL;

    char *colon = strchr(field_start + strlen(search), ':');
    if (!colon)
        return NULL;

    // Skip whitespace after colon
    char *p = colon + 1;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;

    if (*p != '"')
        return NULL;
    p++; // skip opening quote

    // Find closing quote, handling escaped quotes
    char *end = p;
    while (*end) {
        if (*end == '\\' && *(end + 1) == '"') {
            end += 2;
        } else if (*end == '"') {
            break;
        } else {
            end++;
        }
    }

    size_t len = end - p;
    char *result = malloc(len + 1);
    if (!result)
        return NULL;

    // Copy and unescape
    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        if (p[i] == '\\' && i + 1 < len) {
            i++;
            result[j++] = p[i];
        } else {
            result[j++] = p[i];
        }
    }
    result[j] = '\0';

    return result;
}

void
aws_response(int status_code, const char *body) {
    char url[512];
    snprintf(
        url, sizeof(url), "http://%s/2018-06-01/runtime/invocation/%s/response",
        g_runtime_api, g_request_id
    );

    // Escape body for JSON embedding
    // Worst case: every char needs escaping → 2x + some overhead
    size_t body_len = body ? strlen(body) : 0;
    char *escaped = malloc(body_len * 2 + 1);
    if (!escaped) {
        fprintf(stderr, "aws_lambda: out of memory\n");
        return;
    }

    size_t j = 0;
    for (size_t i = 0; i < body_len; i++) {
        switch (body[i]) {
        case '"':
            escaped[j++] = '\\';
            escaped[j++] = '"';
            break;
        case '\\':
            escaped[j++] = '\\';
            escaped[j++] = '\\';
            break;
        case '\n':
            escaped[j++] = '\\';
            escaped[j++] = 'n';
            break;
        case '\r':
            escaped[j++] = '\\';
            escaped[j++] = 'r';
            break;
        case '\t':
            escaped[j++] = '\\';
            escaped[j++] = 't';
            break;
        default:
            escaped[j++] = body[i];
            break;
        }
    }
    escaped[j] = '\0';

    // Build Lambda Function URL response envelope
    size_t resp_size = j + 256;
    char *response = malloc(resp_size);
    if (!response) {
        free(escaped);
        fprintf(stderr, "aws_lambda: out of memory\n");
        return;
    }

    snprintf(
        response, resp_size,
        "{\"statusCode\":%d,\"body\":\"%s\","
        "\"headers\":{\"Content-Type\":\"application/json\"}}",
        status_code, escaped
    );
    free(escaped);

    curl_easy_reset(g_curl);
    curl_easy_setopt(g_curl, CURLOPT_URL, url);
    curl_easy_setopt(g_curl, CURLOPT_POSTFIELDS, response);
    curl_easy_setopt(g_curl, CURLOPT_POSTFIELDSIZE, (long)strlen(response));

    struct curl_slist *headers =
        curl_slist_append(NULL, "Content-Type: application/json");
    curl_easy_setopt(g_curl, CURLOPT_HTTPHEADER, headers);

    CURLcode res = curl_easy_perform(g_curl);
    if (res != CURLE_OK) {
        fprintf(
            stderr, "aws_lambda: failed to send response: %s\n", curl_easy_strerror(res)
        );
    }

    curl_slist_free_all(headers);
    free(response);
}

void
aws_lambda_start(aws_lambda_handler_t handler) {
    g_runtime_api = getenv("AWS_LAMBDA_RUNTIME_API");
    if (!g_runtime_api) {
        fprintf(stderr, "aws_lambda: AWS_LAMBDA_RUNTIME_API not set\n");
        exit(1);
    }

    curl_global_init(CURL_GLOBAL_DEFAULT);
    g_curl = curl_easy_init();
    if (!g_curl) {
        fprintf(stderr, "aws_lambda: failed to init curl\n");
        exit(1);
    }

    char url[512];

    while (1) {
        // Fetch next invocation
        snprintf(
            url, sizeof(url), "http://%s/2018-06-01/runtime/invocation/next",
            g_runtime_api
        );

        MemoryStruct event = {0};
        MemoryStruct hdrs = {0};

        curl_easy_reset(g_curl);
        curl_easy_setopt(g_curl, CURLOPT_URL, url);
        curl_easy_setopt(g_curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(g_curl, CURLOPT_WRITEDATA, &event);
        curl_easy_setopt(g_curl, CURLOPT_HEADERFUNCTION, write_callback);
        curl_easy_setopt(g_curl, CURLOPT_HEADERDATA, &hdrs);

        CURLcode res = curl_easy_perform(g_curl);
        if (res != CURLE_OK) {
            fprintf(
                stderr, "aws_lambda: invocation/next failed: %s\n",
                curl_easy_strerror(res)
            );
            free(event.data);
            free(hdrs.data);
            break;
        }

        if (!hdrs.data || extract_request_id(hdrs.data) != 0) {
            fprintf(stderr, "aws_lambda: missing request ID\n");
            free(event.data);
            free(hdrs.data);
            continue;
        }

        // Extract body from Function URL event
        char *body = aws_json_extract(event.data, "body");
        if (!body)
            body = strdup("");

        // Call user handler
        handler(body);

        free(body);
        free(event.data);
        free(hdrs.data);
    }

    curl_easy_cleanup(g_curl);
    curl_global_cleanup();
}
