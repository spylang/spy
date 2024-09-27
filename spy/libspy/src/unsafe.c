#include "spy.h"

spy_GcRef
WASM_EXPORT(spy_gc_alloc_mem)(size_t size) {
    return spy_GcAlloc(size);
}
