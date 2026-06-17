/*
 * Glue code bridging the system libmagic (the engine behind the Unix `file`
 * command) with SPy's str/bytes types.
 *
 * This is the C half of the out-of-tree `magic` builtin module. Unlike the
 * qrcodegen example, libmagic is an *external* system library (installed via
 * `apt install libmagic-dev` or `brew install libmagic`): we link against it
 * with -lmagic and we do NOT have a WASM build of it. As a consequence the
 * module works only with the C backend; in interpreted mode the corresponding
 * builtin functions raise NotImplementedError (see __init__.py).
 *
 * The C backend calls these functions by their SPy c_name (spy_magic$*).
 */

#include "spyvm_libmagic.h"

#include <magic.h>
#include <string.h>

/*
 * Wrap a NUL-terminated C string into a freshly allocated spy_StrObject. The
 * strings returned by libmagic are owned by the magic_t cookie and become
 * invalid on the next call, so we must copy them out immediately.
 */
static spy_StrObject *make_str(const char *s) {
    if (s == NULL) {
        s = "";
    }
    size_t n = strlen(s);
    spy_StrObject *res = spy_str_alloc(n);
    memcpy(spy_StrObject_UTF8(res), s, n);
    return res;
}

/*
 * Run libmagic on `data` with the given flags and return its textual answer.
 *
 * We open a fresh cookie on every call to keep the SPy-facing API stateless.
 * This is wasteful (the default magic database is reloaded each time) but keeps
 * the example simple; a real binding would cache the cookie.
 */
static spy_StrObject *run_magic(spy_BytesObject *data, int flags) {
    magic_t cookie = magic_open(flags);
    if (cookie == NULL) {
        return make_str("");
    }
    if (magic_load(cookie, NULL) != 0) {
        spy_StrObject *err = make_str(magic_error(cookie));
        magic_close(cookie);
        return err;
    }
    const char *desc =
        magic_buffer(cookie, spy_BytesObject_DATA(data), data->length);
    spy_StrObject *res = make_str(desc);
    magic_close(cookie);
    return res;
}

/*
 * Return a human-readable description of `data`, e.g. "PNG image data, 640 x
 * 480, 8-bit/color RGB". This is what `file` prints by default.
 */
spy_StrObject *spy_magic$describe(spy_BytesObject *data) {
    return run_magic(data, MAGIC_NONE);
}

/*
 * Return the MIME type of `data`, e.g. "image/png". Equivalent to `file
 * --mime-type`.
 */
spy_StrObject *spy_magic$mime(spy_BytesObject *data) {
    return run_magic(data, MAGIC_MIME_TYPE);
}
