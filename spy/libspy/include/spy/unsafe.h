#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"
#include <stddef.h>

void *WASM_EXPORT(spy_nogc_alloc)(size_t size);
void *WASM_EXPORT(spy_raw_alloc)(size_t size);

// note: these are needed to implement unsafe.memcpy&co in the interp (via vm.ll.call),
// but NOT by the C backend. The C backend implements them via IRTags.
void WASM_EXPORT(_spy_memcpy)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memmove)(void *dst, void *src, size_t n);
void WASM_EXPORT(_spy_memset)(void *dst, int value, size_t n);
int32_t WASM_EXPORT(_spy_memcmp)(void *a, void *b, size_t n);

// Aligned allocation wrappers used by the interp (vm.ll.call) path.
// The C backend's $alloc macro calls spy_alloc_aligned_impl directly.
void *WASM_EXPORT(spy_raw_alloc_aligned)(size_t size, size_t alignment);
void *WASM_EXPORT(spy_nogc_alloc_aligned)(size_t size, size_t alignment);

// The base alignment that the underlying allocators (malloc, GC_MALLOC,
// GC_MALLOC_ATOMIC) already guarantee.  When a ptr type requests an
// alignment <= SPY_BASE_ALIGNMENT the $alloc fast path can skip the
// over-allocation / pointer-adjustment dance entirely.
//
// On wasm32 / wasm64, linear-memory allocators return 8-byte-aligned
// pointers.  On native 64-bit targets, malloc and GC_MALLOC guarantee
// 16-byte alignment (alignof(max_align_t)).  We use the larger value so
// that the fast path is taken whenever alignment <= 16, which covers
// every natural SPy type alignment (the largest is 8 for f64/i64).
#if defined(SPY_TARGET_NATIVE) && defined(__LP64__)
#  define SPY_BASE_ALIGNMENT 16
#else
#  define SPY_BASE_ALIGNMENT 8
#endif

// Allocate `n` bytes with at least `alignment`-byte alignment, using the
// given `alloc_func` (one of spy_raw_alloc, spy_nogc_alloc, or the
// GC_MALLOC-based helpers).  When `alignment <= SPY_BASE_ALIGNMENT` the
// allocator already satisfies the request, so we delegate directly with
// no over-allocation, rounding, or base-pointer discarding.  Otherwise we
// over-allocate by `alignment` bytes, round the raw pointer up to the
// next aligned address, and return that.
//
// NOTE: this means the original base pointer is *lost* — the returned
// pointer cannot be passed to free().  This is fine for SPy's GC-managed
// and raw_alloc (never freed) allocators, but would be a problem for a
// general-purpose allocator that needs to reclaim memory.  The over-
// allocation "wastes" at most (alignment - 1) bytes.
static inline void *
spy_alloc_aligned_impl(size_t n, size_t alignment, void *(*alloc_func)(size_t)) {
    if (alignment <= SPY_BASE_ALIGNMENT) {
        // the allocator already guarantees this alignment.
        return alloc_func(n);
    }
    char *raw = (char *)alloc_func(n + alignment);
    uintptr_t a = ((uintptr_t)raw + alignment - 1) & ~(alignment - 1);
    return (void *)a;
}

// Check that `p` is aligned to `alignment` bytes, and return `p` unchanged.
// Used by align_cast[N](ptr) when N strengthens the ptr's alignment claim
// (N > the ptr's current alignment): in SPY_DEBUG builds this panics if
// the check fails, catching a false claim before it can cause misaligned
// accesses further down the line; in RELEASE builds it's a no-op and the
// caller's claim is trusted, so the compiler is free to optimize the call
// away entirely (e.g. when `alignment` is a compile-time constant already
// known to hold).
static inline void *
spy_check_align(void *p, size_t alignment) {
#ifdef SPY_DEBUG
    if ((uintptr_t)p % alignment != 0) {
        spy_panic("PanicError", "align_cast: address not aligned", __FILE__, __LINE__);
    }
#endif
    return p;
}

#ifdef SPY_GC_NONE
#  define spy_gc_alloc(size) spy_nogc_alloc(size)
#  define spy_gc_alloc_pointerless(size) spy_nogc_alloc(size)
#elif SPY_GC_BDWGC
#  include <gc.h>
static inline void *
spy_gc_alloc_bdwgc(size_t size) {
    return GC_MALLOC(size);
}
static inline void *
spy_gc_alloc_pointerless_bdwgc(size_t size) {
    return GC_MALLOC_ATOMIC(size);
}
#  define spy_gc_alloc(size) spy_gc_alloc_bdwgc(size)
#  define spy_gc_alloc_pointerless(size) spy_gc_alloc_pointerless_bdwgc(size)
#else
#  error "no GC selected"
#endif

// spy_gc_alloc and spy_gc_alloc_pointerless (defined just above) are
// function-like MACROS, not real functions: they only expand when
// immediately followed by "(...)". spy_alloc_aligned_impl needs an
// addressable function pointer, so a bare "spy_gc_alloc" (with no call
// parens) does NOT expand and fails to compile. These thin static-inline
// wrappers give us addressable symbols that simply forward to the macros.
static inline void *
spy_gc_alloc_fn(size_t size) {
    return spy_gc_alloc(size);
}

static inline void *
spy_gc_alloc_pointerless_fn(size_t size) {
    return spy_gc_alloc_pointerless(size);
}

// Map an ALLOC_FUNC token (as used by SPY_PTR_FUNCTIONS: raw_alloc,
// gc_alloc, gc_alloc_pointerless) to the actual function symbol that can be
// passed as a function pointer to spy_alloc_aligned_impl. raw_alloc is
// already a real function (spy_raw_alloc), so it maps to itself; gc_alloc
// and gc_alloc_pointerless are macros, so they map to the _fn wrappers
// above instead.
#define _SPY_ALLOC_FN_raw_alloc            spy_raw_alloc
#define _SPY_ALLOC_FN_gc_alloc             spy_gc_alloc_fn
#define _SPY_ALLOC_FN_gc_alloc_pointerless spy_gc_alloc_pointerless_fn

/* Define the struct and accessor functions to represent a managed pointer to
   type T.

   The C backend emits the struct definition:
   typedef struct Ptr_T {
       T *p;
   #ifdef SPY_PTR_CHECKED
       size_t length;
   #endif
   } Ptr_T;

   SPY_PTR_FUNCTIONS(raw_alloc, Ptr_T, T, ALIGNMENT) defines all the accessor
   functions such as Ptr_T$alloc, Ptr_T$load, etc.

   In SPY_RELEASE mode, a managed pointer is just a wrapper around an
   unmanaged C pointer, but in SPY_DEBUG it also contains the length of the
   array it points to, and every access is checked. The length is expressed in
   number of items, NOT size in bytes.

   ALLOC_FUNC is one of:
     - "raw_alloc"             (plain malloc, never collected)
     - "gc_alloc"              (GC_MALLOC: zeroed, scanned)
     - "gc_alloc_pointerless"  (GC_MALLOC_ATOMIC: not zeroed, not
                                scanned; only for pointer-free T)

   ALIGNMENT is the requested alignment in bytes for the allocated
   block.  When it exceeds SPY_BASE_ALIGNMENT, $alloc over-allocates and
   adjusts the pointer via spy_alloc_aligned_impl.
*/

/* Unaligned access helpers.
 *
 * When a ptr type declares an alignment strictly less than the natural
 * alignment of its item type T (e.g. gc_ptr[i32, 1], where
 * alignof(i32) == 4), a plain typed dereference/store is undefined
 * behavior. These helpers route the access through __builtin_memcpy,
 * which compilers lower to the most efficient unaligned access for the
 * target, whenever ALIGNMENT < alignof(T).
 *
 * ALIGNMENT and _Alignof(T) are compile-time constants, so the branch
 * is folded away at compile time: there is zero runtime overhead in the
 * (overwhelmingly common) case where the ptr is naturally aligned.
 */
#define _SPY_PTR_LOAD(T, ALIGNMENT, addr)                                              \
    ((ALIGNMENT) >= _Alignof(T) ? *(addr) : ({                                         \
        T _tmp;                                                                        \
        __builtin_memcpy(&_tmp, (const char *)(addr), sizeof(T));                      \
        _tmp;                                                                          \
    }))

#define _SPY_PTR_STORE(T, ALIGNMENT, addr, rval)                                       \
    do {                                                                               \
        if ((ALIGNMENT) >= _Alignof(T)) {                                              \
            *(addr) = (rval);                                                          \
        } else {                                                                       \
            T _tmp = (rval);                                                           \
            __builtin_memcpy((char *)(addr), &_tmp, sizeof(T));                        \
        }                                                                              \
    } while (0)

#ifdef SPY_DEBUG
#  define SPY_PTR_FUNCTIONS _SPY_PTR_FUNCTIONS_CHECKED
#else
#  define SPY_PTR_FUNCTIONS _SPY_PTR_FUNCTIONS_UNCHECKED
#endif

#define _SPY_PTR_FUNCTIONS_UNCHECKED(ALLOC_FUNC, PTR, T, ALIGNMENT)                    \
    static inline PTR PTR##_from_addr(T *p) {                                          \
        return (PTR){p};                                                               \
    }                                                                                  \
    static inline ptrdiff_t PTR##_get_length(PTR p) {                                  \
        (void)p;                                                                       \
        return 0;                                                                      \
    }                                                                                  \
    static inline PTR PTR##_from_raw(T *p, ptrdiff_t length) {                         \
        (void)length;                                                                  \
        return (PTR){p};                                                               \
    }                                                                                  \
    static inline PTR PTR##$alloc(size_t n) {                                          \
        T *p = (T *)spy_alloc_aligned_impl(                                            \
            sizeof(T) * n, (ALIGNMENT), _SPY_ALLOC_FN_##ALLOC_FUNC                     \
        );                                                                             \
        return (PTR){p};                                                               \
    }                                                                                  \
    static inline T PTR##$deref(PTR p) {                                               \
        return _SPY_PTR_LOAD(T, ALIGNMENT, p.p);                                       \
    }                                                                                  \
    static inline T PTR##$getitem_byval(PTR p, ptrdiff_t i) {                          \
        return _SPY_PTR_LOAD(T, ALIGNMENT, p.p + i);                                   \
    }                                                                                  \
    static inline PTR PTR##$getitem_byref(PTR p, ptrdiff_t i) {                        \
        return PTR##_from_addr(p.p + i);                                               \
    }                                                                                  \
    static inline void PTR##$store(PTR p, ptrdiff_t i, T v) {                          \
        _SPY_PTR_STORE(T, ALIGNMENT, p.p + i, v);                                      \
    }                                                                                  \
    static inline bool PTR##$__eq__(PTR p0, PTR p1) {                                  \
        return p0.p == p1.p;                                                           \
    }                                                                                  \
    static inline bool PTR##$__ne__(PTR p0, PTR p1) {                                  \
        return p0.p != p1.p;                                                           \
    }                                                                                  \
    static inline bool PTR##$to_bool(PTR p) {                                          \
        return p.p;                                                                    \
    }                                                                                  \
    static inline int32_t PTR##$to_addr(PTR p) {                                       \
        /* NOTE: truncates to 32 bits. Only meaningful on wasm32-like                  \
           targets where addresses actually fit in 32 bits. See the                    \
           comment on W_MemLoc.addr in spy/vm/modules/unsafe/ptr.py. */                \
        return (int32_t)(uintptr_t)p.p;                                                \
    }

#define _SPY_PTR_FUNCTIONS_CHECKED(ALLOC_FUNC, PTR, T, ALIGNMENT)                      \
    static inline PTR PTR##_from_addr(T *p) {                                          \
        return (PTR){p, 1};                                                            \
    }                                                                                  \
    static inline ptrdiff_t PTR##_get_length(PTR p) {                                  \
        return p.length;                                                               \
    }                                                                                  \
    static inline PTR PTR##_from_raw(T *p, ptrdiff_t length) {                         \
        return (PTR){p, length};                                                       \
    }                                                                                  \
    static inline PTR PTR##$alloc(size_t n) {                                          \
        T *p = (T *)spy_alloc_aligned_impl(                                            \
            sizeof(T) * n, (ALIGNMENT), _SPY_ALLOC_FN_##ALLOC_FUNC                     \
        );                                                                             \
        return (PTR){p, (ptrdiff_t)n};                                                 \
    }                                                                                  \
    static inline T PTR##$deref(PTR p) {                                               \
        return _SPY_PTR_LOAD(T, ALIGNMENT, p.p);                                       \
    }                                                                                  \
    static inline T PTR##$getitem_byval(PTR p, ptrdiff_t i) {                          \
        if (p.p == NULL)                                                               \
            spy_panic(                                                                 \
                "PanicError", "cannot dereference NULL pointer", __FILE__, __LINE__    \
            );                                                                         \
        if (i < 0 || i >= p.length)                                                    \
            spy_panic("PanicError", "ptr_getitem out of bounds", __FILE__, __LINE__);  \
        return _SPY_PTR_LOAD(T, ALIGNMENT, p.p + i);                                   \
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
        _SPY_PTR_STORE(T, ALIGNMENT, p.p + i, v);                                      \
    }                                                                                  \
    static inline bool PTR##$__eq__(PTR p0, PTR p1) {                                  \
        return p0.p == p1.p && p0.length == p1.length;                                 \
    }                                                                                  \
    static inline bool PTR##$__ne__(PTR p0, PTR p1) {                                  \
        return p0.p != p1.p || p0.length != p1.length;                                 \
    }                                                                                  \
    static inline bool PTR##$to_bool(PTR p) {                                          \
        return p.p;                                                                    \
    }                                                                                  \
    static inline int32_t PTR##$to_addr(PTR p) {                                       \
        /* NOTE: truncates to 32 bits. Only meaningful on wasm32-like                  \
           targets where addresses actually fit in 32 bits. See the                    \
           comment on W_MemLoc.addr in spy/vm/modules/unsafe/ptr.py. */                \
        return (int32_t)(uintptr_t)p.p;                                                \
    }

/* gc_ptr[u8] is predeclared here, see also cstructwriter.py:emit_PtrType.
   Make sure that they stay in sync. */
typedef struct spy_unsafe$gc_ptr__builtins$u8 {
    uint8_t *p;
#ifdef SPY_DEBUG
    ptrdiff_t length;
#endif
} spy_unsafe$gc_ptr__builtins$u8;

SPY_PTR_FUNCTIONS(gc_alloc, spy_unsafe$gc_ptr__builtins$u8, uint8_t, 1)
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
#  define spy_ptr_setbytes(dst, value, n)                                              \
      do {                                                                             \
          if ((size_t)(n) > (size_t)(dst).length)                                      \
              spy_panic(                                                               \
                  "PanicError", "ptr_setbytes out of bounds", __FILE__, __LINE__       \
              );                                                                       \
          memset((dst).p, (value), (n) * sizeof(*(dst).p));                            \
      } while (0)
#else
#  define spy_ptr_setbytes(dst, value, n)                                              \
      memset((dst).p, (value), (n) * sizeof(*(dst).p))
#endif

#ifdef SPY_DEBUG
#  define spy_ptr_setbytes_slice(dst, ds, de, value)                                   \
      do {                                                                             \
          ptrdiff_t _spy_n = (de) - (ds);                                              \
          if (_spy_n < 0 || (ds) < 0 || (de) > (dst).length)                           \
              spy_panic(                                                               \
                  "PanicError", "ptr_setbytes_slice out of bounds", __FILE__, __LINE__ \
              );                                                                       \
          memset((dst).p + (ds), (value), _spy_n * sizeof(*(dst).p));                  \
      } while (0)
#else
#  define spy_ptr_setbytes_slice(dst, ds, de, value)                                   \
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
