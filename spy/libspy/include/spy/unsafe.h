#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"

void *WASM_EXPORT(spy_gc_alloc)(size_t size);
void *WASM_EXPORT(spy_raw_alloc)(size_t size);

// When compiling with bdwgc, override spy_gc_alloc with an inline that calls
// GC_MALLOC. This takes precedence over the function in libspy.a.
#ifdef SPY_GC_BDWGC
#include <gc.h>
static inline void *spy_gc_alloc_bdwgc(size_t size) { return GC_MALLOC(size); }
#define spy_gc_alloc(size) spy_gc_alloc_bdwgc(size)
#endif

/* Define the struct and accessor functions to represent a managed pointer to
   type T.

   The C backend emits the struct definition:
   typedef struct Ptr_T {
       T *p;
   #ifdef SPY_PTR_CHECKED
       size_t length;
   #endif
   } Ptr_T;

   SPY_PTR_FUNCTIONS(raw, Ptr_T, T) defines all the accessor functions such as
   Ptr_T$alloc, Ptr_T$load, etc.

   In SPY_RELEASE mode, a managed pointer is just a wrapper around an
   unmanaged C pointer, but in SPY_DEBUG it also contains the length of the
   array it points to, and every access is checked. The length is expressed in
   number of items, NOT size in bytes.
*/
#ifdef SPY_DEBUG
#  define SPY_PTR_FUNCTIONS _SPY_PTR_FUNCTIONS_CHECKED
#else
#  define SPY_PTR_FUNCTIONS _SPY_PTR_FUNCTIONS_UNCHECKED
#endif

#define _SPY_PTR_FUNCTIONS_UNCHECKED(MEMKIND, PTR, T)                                  \
    static inline PTR PTR##_from_addr(T *p) {                                          \
        return (PTR){p};                                                               \
    }                                                                                  \
    static inline PTR PTR##$alloc(size_t n) {                                          \
        return (PTR){spy_##MEMKIND##_alloc(sizeof(T) * n)};                            \
    }                                                                                  \
    static inline T PTR##$deref(PTR p) {                                               \
        return *(p.p);                                                                 \
    }                                                                                  \
    static inline T PTR##$getitem_byval(PTR p, ptrdiff_t i) {                          \
        return p.p[i];                                                                 \
    }                                                                                  \
    static inline PTR PTR##$getitem_byref(PTR p, ptrdiff_t i) {                        \
        return PTR##_from_addr(p.p + i);                                               \
    }                                                                                  \
    static inline void PTR##$store(PTR p, ptrdiff_t i, T v) {                          \
        p.p[i] = v;                                                                    \
    }                                                                                  \
    static inline bool PTR##$__eq__(PTR p0, PTR p1) {                                  \
        return p0.p == p1.p;                                                           \
    }                                                                                  \
    static inline bool PTR##$__ne__(PTR p0, PTR p1) {                                  \
        return p0.p != p1.p;                                                           \
    }                                                                                  \
    static inline bool PTR##$to_bool(PTR p) {                                          \
        return p.p;                                                                    \
    }

#define _SPY_PTR_FUNCTIONS_CHECKED(MEMKIND, PTR, T)                                    \
    static inline PTR PTR##_from_addr(T *p) {                                          \
        return (PTR){p, 1};                                                            \
    }                                                                                  \
    static inline PTR PTR##$alloc(size_t n) {                                          \
        return (PTR){spy_##MEMKIND##_alloc(sizeof(T) * n), n};                         \
    }                                                                                  \
    static inline T PTR##$deref(PTR p) {                                               \
        return *(p.p);                                                                 \
    }                                                                                  \
    static inline T PTR##$getitem_byval(PTR p, ptrdiff_t i) {                          \
        if (p.p == NULL)                                                               \
            spy_panic(                                                                 \
                "PanicError", "cannot dereference NULL pointer", __FILE__, __LINE__    \
            );                                                                         \
        if (i < 0 || i >= p.length)                                                    \
            spy_panic("PanicError", "ptr_getitem out of bounds", __FILE__, __LINE__);  \
        return p.p[i];                                                                 \
    }                                                                                  \
    static inline PTR PTR##$getitem_byref(PTR p, ptrdiff_t i) {                        \
        if (p.p == NULL)                                                               \
            spy_panic(                                                                 \
                "PanicError", "cannot dereference NULL pointer", __FILE__, __LINE__    \
            );                                                                         \
        if (i < 0 || i >= p.length)                                                    \
            spy_panic("PanicError", "ptr_getitem out of bounds", __FILE__, __LINE__);  \
        return PTR##_from_addr(p.p + i);                                               \
    }                                                                                  \
    static inline void PTR##$store(PTR p, ptrdiff_t i, T v) {                          \
        if (p.p == NULL)                                                               \
            spy_panic(                                                                 \
                "PanicError", "cannot dereference NULL pointer", __FILE__, __LINE__    \
            );                                                                         \
        if (i < 0 || i >= p.length)                                                    \
            spy_panic("PanicError", "ptr_store out of bounds", __FILE__, __LINE__);    \
        p.p[i] = v;                                                                    \
    }                                                                                  \
    static inline bool PTR##$__eq__(PTR p0, PTR p1) {                                  \
        return p0.p == p1.p && p0.length == p1.length;                                 \
    }                                                                                  \
    static inline bool PTR##$__ne__(PTR p0, PTR p1) {                                  \
        return p0.p != p1.p || p0.length != p1.length;                                 \
    }                                                                                  \
    static inline bool PTR##$to_bool(PTR p) {                                          \
        return p.p;                                                                    \
    }

#endif /* SPY_UNSAFE_H */
