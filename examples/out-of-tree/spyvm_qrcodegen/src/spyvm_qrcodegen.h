#ifndef SPYVM_QRCODEGEN_H
#define SPYVM_QRCODEGEN_H

#include <spy.h>
#include <spy/bytes.h>
#include <spy/str.h>
#include <stdbool.h>
#include <stdint.h>

spy_BytesObject *spy_qrcodegen$encode(spy_StrObject *text);
int32_t spy_qrcodegen$get_size(spy_BytesObject *qr);
bool spy_qrcodegen$get_module(spy_BytesObject *qr, int32_t x, int32_t y);

#endif /* SPYVM_QRCODEGEN_H */
