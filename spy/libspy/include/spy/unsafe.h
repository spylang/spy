#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"
#include <stddef.h>

void *WASM_EXPORT(spy_gc_alloc)(size_t size);
void *WASM_EXPORT(spy_raw_alloc)(size_t size);

// note: these are needed to implement unsafe.memcpy&co in the interp (via vm.ll.call),
// but NOT by the C backend. The C backend implements them via IRTags.
void WASM_EXPORT(_spy_memcpy)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memmove)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memset)(void *dst, int value, size_t n);
int32_t WASM_EXPORT(_spy_memcmp)(void *a, void *b, size_t n);

// When compiling with bdwgc, override spy_gc_alloc with an inline that calls
// GC_MALLOC. This takes precedence over the function in libspy.a.
#ifdef SPY_GC_BDWGC
#  include <gc.h>
static inline void *
spy_gc_alloc_bdwgc(size_t size) {
    return GC_MALLOC(size);
}
#  define spy_gc_alloc(size) spy_gc_alloc_bdwgc(size)
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

/* gc_ptr[u8] is predeclared here, see also cstructwriter.py:emit_PtrType.
   Make sure that they stay in sync. */
typedef struct spy_unsafe$gc_ptr__builtins$u8 {
    uint8_t *p;
#ifdef SPY_DEBUG
    ptrdiff_t length;
#endif
} spy_unsafe$gc_ptr__builtins$u8;

SPY_PTR_FUNCTIONS(gc, spy_unsafe$gc_ptr__builtins$u8, uint8_t)
#define spy_unsafe$gc_ptr__builtins$u8$NULL ((spy_unsafe$gc_ptr__builtins$u8){0})

// short alias for manual use
typedef spy_unsafe$gc_ptr__builtins$u8 spy_gc_ptr_u8;

/* memcpy/memmove/memset/memcmp macros for the C backend.
   In SPY_DEBUG they check bounds via the .length field; in SPY_RELEASE they
   expand to bare libc calls with zero overhead. */
#ifdef SPY_DEBUG
#  define spy_memcpy(dst, src, n)                                                      \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic("PanicError", "memcpy dst out of bounds", __FILE__, __LINE__); \
          if ((size_t)(n) > (size_t)(src).length)                                      \
              spy_panic("PanicError", "memcpy src out of bounds", __FILE__, __LINE__); \
          memcpy((dst).p, (src).p, (n));                                               \
      } while (0)
#else
#  define spy_memcpy(dst, src, n) memcpy((dst).p, (src).p, (n))
#endif

#ifdef SPY_DEBUG
#  define spy_memmove(dst, src, n)                                                     \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "memmove dst out of bounds", __FILE__, __LINE__        \
              );                                                                       \
          if ((size_t)(n) > (size_t)(src).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "memmove src out of bounds", __FILE__, __LINE__        \
              );                                                                       \
          memmove((dst).p, (src).p, (n));                                              \
      } while (0)
#else
#  define spy_memmove(dst, src, n) memmove((dst).p, (src).p, (n))
#endif

#ifdef SPY_DEBUG
#  define spy_memset(dst, value, n)                                                    \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic("PanicError", "memset out of bounds", __FILE__, __LINE__);     \
          memset((dst).p, (value), (n));                                               \
      } while (0)
#else
#  define spy_memset(dst, value, n) memset((dst).p, (value), (n))
#endif

// spy_memcmp needs to yield a value; ternary chain works on all compilers.
// spy_panic is NORETURN so the ", 0" arms are dead code but satisfy the type.
#ifdef SPY_DEBUG
#  define spy_memcmp(a, b, n)                                                          \
      ((size_t)(n) > (size_t)(a).length                                                \
           ? (spy_panic("PanicError", "memcmp a out of bounds", __FILE__, __LINE__),   \
              0)                                                                       \
       : (size_t)(n) > (size_t)(b).length                                              \
           ? (spy_panic("PanicError", "memcmp b out of bounds", __FILE__, __LINE__),   \
              0)                                                                       \
           : memcmp((a).p, (b).p, (n)))
#else
#  define spy_memcmp(a, b, n) memcmp((a).p, (b).p, (n))
#endif

#endif /* SPY_UNSAFE_H */
