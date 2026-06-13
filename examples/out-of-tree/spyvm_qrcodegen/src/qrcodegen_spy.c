/*
 * Glue code bridging the qrcodegen C library with SPy's str/bytes types.
 *
 * This is the C half of the out-of-tree `qrcodegen` builtin module. It
 * #includes libspy's public headers normally and calls libspy functions
 * (spy_bytes_alloc, ...) directly; when loaded in interpreted mode it is
 * statically linked together with libspy into a single WASM reactor module.
 *
 * The C backend calls these functions by their SPy c_name (spy_qrcodegen$*).
 * WASM_EXPORT gives them the same name as the wasm export, which is also
 * spy_qrcodegen$* on wasi (WASM_EXPORT is a no-op on native).
 */

#include "qrcodegen_spy.h"
#include "qrcodegen.h"

#include <string.h>
#include <stdlib.h>

/*
 * Encode `text` into a QR Code and return the resulting qrcode buffer as a
 * spy_BytesObject. On failure (text too long) an empty bytes object is
 * returned.
 *
 * The returned bytes can be passed to get_size() and get_module().
 */
spy_BytesObject *WASM_EXPORT(spy_qrcodegen$encode)(spy_StrObject *text) {
    // spy_StrObject is not NUL-terminated, so copy into a NUL-terminated
    // buffer for qrcodegen_encodeText.
    size_t n = text->length;
    uint8_t tempbuf[qrcodegen_BUFFER_LEN_MAX];
    uint8_t qrbuf[qrcodegen_BUFFER_LEN_MAX];

    char *ctext = (char *)malloc(n + 1);
    memcpy(ctext, spy_StrObject_CHARS(text), n);
    ctext[n] = '\0';

    bool ok = qrcodegen_encodeText(
        ctext, tempbuf, qrbuf, qrcodegen_Ecc_MEDIUM, qrcodegen_VERSION_MIN,
        qrcodegen_VERSION_MAX, qrcodegen_Mask_AUTO, true
    );
    free(ctext);

    if (!ok) {
        return spy_bytes_alloc(0);
    }

    // qrcodegen functions read at most qrcodegen_getSize()-derived bytes from
    // qrbuf, but we copy the whole worst-case buffer for simplicity.
    spy_BytesObject *res = spy_bytes_alloc(qrcodegen_BUFFER_LEN_MAX);
    memcpy(spy_BytesObject_DATA(res), qrbuf, qrcodegen_BUFFER_LEN_MAX);
    return res;
}

/*
 * Return the side length of the QR Code stored in `qr`, or 0 if `qr` is empty
 * (i.e. encoding failed).
 */
int32_t WASM_EXPORT(spy_qrcodegen$get_size)(spy_BytesObject *qr) {
    if (qr->length == 0) {
        return 0;
    }
    return qrcodegen_getSize(spy_BytesObject_DATA(qr));
}

/*
 * Return whether the module (pixel) at (x, y) is dark.
 */
bool WASM_EXPORT(spy_qrcodegen$get_module)(spy_BytesObject *qr, int32_t x, int32_t y) {
    return qrcodegen_getModule(spy_BytesObject_DATA(qr), x, y);
}
