#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"
#include <stddef.h>

void *WASM_EXPORT(spy_gc_alloc)(size_t size);
void *WASM_EXPORT(spy_gc_alloc_atomic)(size_t size);
void *WASM_EXPORT(spy_raw_alloc)(size_t size);

// note: these are needed to implement unsafe.memcpy&co in the interp (via vm.ll.call),
// but NOT by the C backend. The C backend implements them via IRTags.
void WASM_EXPORT(_spy_memcpy)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memmove)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memset)(void *dst, int value, size_t n);
int32_t WASM_EXPORT(_spy_memcmp)(void *a, void *b, size_t n);

// When compiling with bdwgc, override spy_gc_alloc with an inline that calls
// GC_MALLOC. This takes precedence over the function in libspy.a.
//
// spy_gc_alloc_atomic uses GC_MALLOC_ATOMIC instead: it tells the collector
// that the allocated block contains NO pointers, so (a) it doesn't need to
// be scanned during collection, and (b) bdwgc does not zero it before
// returning it (unlike GC_MALLOC). This is the right choice for buffers of
// primitive types (e.g. arrays of f64/i32/u8/...), and is significantly
// faster. It must NEVER be used for memory that may contain gc_ptr/gc_ref
// values, or those objects could be collected while still reachable.
#ifdef SPY_GC_BDWGC
#  include <gc.h>
static inline void *
spy_gc_alloc_bdwgc(size_t size) {
    return GC_MALLOC(size);
}
static inline void *
spy_gc_alloc_atomic_bdwgc(size_t size) {
    return GC_MALLOC_ATOMIC(size);
}
#  define spy_gc_alloc(size) spy_gc_alloc_bdwgc(size)
#  define spy_gc_alloc_atomic(size) spy_gc_alloc_atomic_bdwgc(size)
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

   MEMKIND is one of "raw", "gc", or "gc_atomic":
     - "raw"       -> spy_raw_alloc        (plain malloc, never collected)
     - "gc"        -> spy_gc_alloc         (GC_MALLOC: zeroed, scanned)
     - "gc_atomic" -> spy_gc_alloc_atomic  (GC_MALLOC_ATOMIC: not zeroed, not
                                             scanned; only for pointer-free T)
   PTR$alloc expands MEMKIND via spy_##MEMKIND##_alloc(...); the alias below
   makes spy_gc_atomic_alloc resolve to spy_gc_alloc_atomic.
*/
#define spy_gc_atomic_alloc(size) spy_gc_alloc_atomic(size)

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
        return (PTR){(T*)spy_##MEMKIND##_alloc(sizeof(T) * n)};                        \
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
        return (PTR){(T*)spy_##MEMKIND##_alloc(sizeof(T) * n), (ptrdiff_t) n};         \
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

/* ptr_copy/ptr_move/ptr_setbytes/ptr_cmp macros for the C backend.
   In SPY_DEBUG they check bounds via the .length field; in SPY_RELEASE they
   expand to bare libc calls with zero overhead.

   Unlike C's memcpy/memmove/memset/memcmp, `n` is the number of ITEMS, not
   bytes — matching Rust's ptr::copy{,_nonoverlapping}, Java's
   System.arraycopy, C#'s Array.Copy, and Go's copy. */
#ifdef SPY_DEBUG
#  define spy_ptr_copy(dst, src, n)                                                    \
      do {                                                                             \
          size_t _spy_nb = (size_t)(n) * sizeof(*(dst).p);                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "ptr_copy dst out of bounds", __FILE__, __LINE__       \
              );                                                                       \
          if ((size_t)(n) > (size_t)(src).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "ptr_copy src out of bounds", __FILE__, __LINE__       \
              );                                                                       \
          if ((char *)(dst).p < (char *)(src).p + _spy_nb &&                           \
              (char *)(src).p < (char *)(dst).p + _spy_nb)                             \
              spy_panic("PanicError", "ptr_copy regions overlap", __FILE__, __LINE__); \
          memcpy((dst).p, (src).p, _spy_nb);                                           \
      } while (0)
#else
#  define spy_ptr_copy(dst, src, n) memcpy((dst).p, (src).p, (n) * sizeof(*(dst).p))
#endif

/* ptr_copy_slice(dst, dst_start, dst_end, src, src_start, src_end):
   copy items in src[src_start:src_end] to dst[dst_start:dst_end].
   Both slices must have the same length; bounds are checked in SPY_DEBUG. */
#ifdef SPY_DEBUG
#  define spy_ptr_copy_slice(dst, ds, de, src, ss, se)                                 \
      do {                                                                             \
          ptrdiff_t _spy_n = (de) - (ds);                                              \
          if (_spy_n != (se) - (ss))                                                   \
              spy_panic(                                                               \
                  "PanicError", "ptr_copy_slice length mismatch", __FILE__, __LINE__   \
              );                                                                       \
          if (_spy_n < 0 || (ds) < 0 || (de) > (dst).length)                           \
              spy_panic(                                                               \
                  "PanicError", "ptr_copy_slice dst out of bounds", __FILE__, __LINE__ \
              );                                                                       \
          if ((ss) < 0 || (se) > (src).length)                                         \
              spy_panic(                                                               \
                  "PanicError", "ptr_copy_slice src out of bounds", __FILE__, __LINE__ \
              );                                                                       \
          {                                                                            \
              size_t _spy_nb = (size_t)_spy_n * sizeof(*(dst).p);                      \
              char *_spy_d = (char *)((dst).p + (ds));                                 \
              char *_spy_s = (char *)((src).p + (ss));                                 \
              if (_spy_d < _spy_s + _spy_nb && _spy_s < _spy_d + _spy_nb)              \
                  spy_panic(                                                           \
                      "PanicError", "ptr_copy_slice regions overlap", __FILE__,        \
                      __LINE__                                                         \
                  );                                                                   \
              memcpy(_spy_d, _spy_s, _spy_nb);                                         \
          }                                                                            \
      } while (0)
#else
#  define spy_ptr_copy_slice(dst, ds, de, src, ss, se)                                 \
      memcpy((dst).p + (ds), (src).p + (ss), ((de) - (ds)) * sizeof(*(dst).p))
#endif

#ifdef SPY_DEBUG
#  define spy_ptr_move(dst, src, n)                                                    \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "ptr_move dst out of bounds", __FILE__, __LINE__       \
              );                                                                       \
          if ((size_t)(n) > (size_t)(src).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "ptr_move src out of bounds", __FILE__, __LINE__       \
              );                                                                       \
          memmove((dst).p, (src).p, (n) * sizeof(*(dst).p));                           \
      } while (0)
#else
#  define spy_ptr_move(dst, src, n) memmove((dst).p, (src).p, (n) * sizeof(*(dst).p))
#endif

#ifdef SPY_DEBUG
#  define spy_ptr_move_slice(dst, ds, de, src, ss, se)                                 \
      do {                                                                             \
          ptrdiff_t _spy_n = (de) - (ds);                                              \
          if (_spy_n != (se) - (ss))                                                   \
              spy_panic(                                                               \
                  "PanicError", "ptr_move_slice length mismatch", __FILE__, __LINE__   \
              );                                                                       \
          if (_spy_n < 0 || (ds) < 0 || (de) > (dst).length)                           \
              spy_panic(                                                               \
                  "PanicError", "ptr_move_slice dst out of bounds", __FILE__, __LINE__ \
              );                                                                       \
          if ((ss) < 0 || (se) > (src).length)                                         \
              spy_panic(                                                               \
                  "PanicError", "ptr_move_slice src out of bounds", __FILE__, __LINE__ \
              );                                                                       \
          memmove((dst).p + (ds), (src).p + (ss), _spy_n * sizeof(*(dst).p));          \
      } while (0)
#else
#  define spy_ptr_move_slice(dst, ds, de, src, ss, se)                                 \
      memmove((dst).p + (ds), (src).p + (ss), ((de) - (ds)) * sizeof(*(dst).p))
#endif

#ifdef SPY_DEBUG
#  define spy_ptr_setbytes(dst, value, n)                                                   \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic("PanicError", "ptr_setbytes out of bounds", __FILE__, __LINE__);    \
          memset((dst).p, (value), (n) * sizeof(*(dst).p));                            \
      } while (0)
#else
#  define spy_ptr_setbytes(dst, value, n) memset((dst).p, (value), (n) * sizeof(*(dst).p))
#endif

#ifdef SPY_DEBUG
#  define spy_ptr_setbytes_slice(dst, ds, de, value)                                        \
      do {                                                                             \
          ptrdiff_t _spy_n = (de) - (ds);                                              \
          if (_spy_n < 0 || (ds) < 0 || (de) > (dst).length)                           \
              spy_panic(                                                               \
                  "PanicError", "ptr_setbytes_slice out of bounds", __FILE__, __LINE__      \
              );                                                                       \
          memset((dst).p + (ds), (value), _spy_n * sizeof(*(dst).p));                  \
      } while (0)
#else
#  define spy_ptr_setbytes_slice(dst, ds, de, value)                                        \
      memset((dst).p + (ds), (value), ((de) - (ds)) * sizeof(*(dst).p))
#endif

// spy_ptr_cmp needs to yield a value; ternary chain works on all compilers.
// spy_panic is NORETURN so the ", 0" arms are dead code but satisfy the type.
#ifdef SPY_DEBUG
#  define spy_ptr_cmp(a, b, n)                                                         \
      ((size_t)(n) > (size_t)(a).length                                                \
           ? (spy_panic("PanicError", "ptr_cmp a out of bounds", __FILE__, __LINE__),  \
              0)                                                                       \
       : (size_t)(n) > (size_t)(b).length                                              \
           ? (spy_panic("PanicError", "ptr_cmp b out of bounds", __FILE__, __LINE__),  \
              0)                                                                       \
           : memcmp((a).p, (b).p, (n) * sizeof(*(a).p)))
#else
#  define spy_ptr_cmp(a, b, n) memcmp((a).p, (b).p, (n) * sizeof(*(a).p))
#endif

// spy_ptr_cmp_slice yields a value too; same ternary trick.
#ifdef SPY_DEBUG
#  define spy_ptr_cmp_slice(a, as_, ae, b, bs, be)                                     \
      (((ae) - (as_)) != ((be) - (bs))                                                 \
           ? (spy_panic(                                                               \
                  "PanicError", "ptr_cmp_slice length mismatch", __FILE__, __LINE__    \
              ),                                                                       \
              0)                                                                       \
       : ((ae) - (as_)) < 0 || (as_) < 0 || (ae) > (a).length                          \
           ? (spy_panic(                                                               \
                  "PanicError", "ptr_cmp_slice a out of bounds", __FILE__, __LINE__    \
              ),                                                                       \
              0)                                                                       \
       : (bs) < 0 || (be) > (b).length                                                 \
           ? (spy_panic(                                                               \
                  "PanicError", "ptr_cmp_slice b out of bounds", __FILE__, __LINE__    \
              ),                                                                       \
              0)                                                                       \
           : memcmp((a).p + (as_), (b).p + (bs), ((ae) - (as_)) * sizeof(*(a).p)))
#else
#  define spy_ptr_cmp_slice(a, as_, ae, b, bs, be)                                     \
      memcmp((a).p + (as_), (b).p + (bs), ((ae) - (as_)) * sizeof(*(a).p))
#endif

#endif /* SPY_UNSAFE_H */
