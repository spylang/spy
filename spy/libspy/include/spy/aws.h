#ifndef SPY_AWS_H
#define SPY_AWS_H

#include "spy/str.h"

#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* SPy aws module - loop-based API for AWS Lambda Function URLs.
 *
 * Implements the AWS Lambda runtime API using libcurl, exposing a
 * sequential loop interface instead of the callback-based one.
 */

typedef struct {
    char *data;
    size_t size;
} spy_aws_mem;

static const char *spy_aws_runtime_api;
static char spy_aws_request_id[256];
static CURL *spy_aws_curl;

static size_t
spy_aws_write_cb(void *ptr, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    spy_aws_mem *mem = (spy_aws_mem *)userp;
    char *p = realloc(mem->data, mem->size + realsize + 1);
    if (!p)
        return 0;
    mem->data = p;
    memcpy(&mem->data[mem->size], ptr, realsize);
    mem->size += realsize;
    mem->data[mem->size] = 0;
    return realsize;
}

static int
spy_aws_extract_request_id(const char *headers) {
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
    if (len >= sizeof(spy_aws_request_id))
        return -1;
    memcpy(spy_aws_request_id, start, len);
    spy_aws_request_id[len] = '\0';
    return 0;
}

/* Simple JSON string field extractor (same logic as aws_json_extract). */
static char *
spy_aws_json_extract(const char *json, const char *field) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", field);
    char *fs = strstr(json, search);
    if (!fs)
        return NULL;
    char *colon = strchr(fs + strlen(search), ':');
    if (!colon)
        return NULL;
    char *p = colon + 1;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    if (*p != '"')
        return NULL;
    p++;
    char *end = p;
    while (*end) {
        if (*end == '\\' && *(end + 1) == '"')
            end += 2;
        else if (*end == '"')
            break;
        else
            end++;
    }
    size_t len = end - p;
    char *result = malloc(len + 1);
    if (!result)
        return NULL;
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

static inline void
spy_aws$lambda_init(void) {
    spy_aws_runtime_api = getenv("AWS_LAMBDA_RUNTIME_API");
    if (!spy_aws_runtime_api) {
        fprintf(stderr, "aws: AWS_LAMBDA_RUNTIME_API not set\n");
        exit(1);
    }
    curl_global_init(CURL_GLOBAL_DEFAULT);
    spy_aws_curl = curl_easy_init();
    if (!spy_aws_curl) {
        fprintf(stderr, "aws: failed to init curl\n");
        exit(1);
    }
}

/* Fetch the next Lambda invocation and return the HTTP body as a spy_Str. */
static inline spy_Str *
spy_aws$lambda_next_body(void) {
    char url[512];
    snprintf(url, sizeof(url),
             "http://%s/2018-06-01/runtime/invocation/next",
             spy_aws_runtime_api);

    spy_aws_mem event = {0};
    spy_aws_mem hdrs = {0};

    curl_easy_reset(spy_aws_curl);
    curl_easy_setopt(spy_aws_curl, CURLOPT_URL, url);
    curl_easy_setopt(spy_aws_curl, CURLOPT_WRITEFUNCTION, spy_aws_write_cb);
    curl_easy_setopt(spy_aws_curl, CURLOPT_WRITEDATA, &event);
    curl_easy_setopt(spy_aws_curl, CURLOPT_HEADERFUNCTION, spy_aws_write_cb);
    curl_easy_setopt(spy_aws_curl, CURLOPT_HEADERDATA, &hdrs);

    CURLcode res = curl_easy_perform(spy_aws_curl);
    if (res != CURLE_OK) {
        fprintf(stderr, "aws: invocation/next failed: %s\n",
                curl_easy_strerror(res));
        free(event.data);
        free(hdrs.data);
        exit(1);
    }

    if (!hdrs.data || spy_aws_extract_request_id(hdrs.data) != 0) {
        fprintf(stderr, "aws: missing request ID in response headers\n");
        free(event.data);
        free(hdrs.data);
        exit(1);
    }

    char *body = spy_aws_json_extract(event.data, "body");
    if (!body)
        body = strdup("");

    size_t len = strlen(body);
    spy_Str *result = spy_str_alloc(len);
    memcpy((char *)result->utf8, body, len);

    free(body);
    free(event.data);
    free(hdrs.data);
    return result;
}

/* Send an HTTP response for the current Lambda invocation. */
static inline void
spy_aws$response(int32_t status_code, spy_Str *body) {
    char url[512];
    snprintf(url, sizeof(url),
             "http://%s/2018-06-01/runtime/invocation/%s/response",
             spy_aws_runtime_api, spy_aws_request_id);

    size_t body_len = body->length;
    char *escaped = malloc(body_len * 2 + 1);
    if (!escaped) {
        fprintf(stderr, "aws: out of memory\n");
        return;
    }

    size_t j = 0;
    for (size_t i = 0; i < body_len; i++) {
        switch (body->utf8[i]) {
        case '"':  escaped[j++] = '\\'; escaped[j++] = '"'; break;
        case '\\': escaped[j++] = '\\'; escaped[j++] = '\\'; break;
        case '\n': escaped[j++] = '\\'; escaped[j++] = 'n'; break;
        case '\r': escaped[j++] = '\\'; escaped[j++] = 'r'; break;
        case '\t': escaped[j++] = '\\'; escaped[j++] = 't'; break;
        default:   escaped[j++] = body->utf8[i]; break;
        }
    }
    escaped[j] = '\0';

    size_t resp_size = j + 256;
    char *response = malloc(resp_size);
    if (!response) {
        free(escaped);
        fprintf(stderr, "aws: out of memory\n");
        return;
    }

    snprintf(response, resp_size,
             "{\"statusCode\":%d,\"body\":\"%s\","
             "\"headers\":{\"Content-Type\":\"application/json\"}}",
             status_code, escaped);
    free(escaped);

    curl_easy_reset(spy_aws_curl);
    curl_easy_setopt(spy_aws_curl, CURLOPT_URL, url);
    curl_easy_setopt(spy_aws_curl, CURLOPT_POSTFIELDS, response);
    curl_easy_setopt(spy_aws_curl, CURLOPT_POSTFIELDSIZE, (long)strlen(response));

    struct curl_slist *headers =
        curl_slist_append(NULL, "Content-Type: application/json");
    curl_easy_setopt(spy_aws_curl, CURLOPT_HTTPHEADER, headers);

    CURLcode res = curl_easy_perform(spy_aws_curl);
    if (res != CURLE_OK) {
        fprintf(stderr, "aws: failed to send response: %s\n",
                curl_easy_strerror(res));
    }

    curl_slist_free_all(headers);
    free(response);
}

#endif /* SPY_AWS_H */
