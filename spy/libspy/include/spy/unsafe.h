#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"

spy_GcRef
WASM_EXPORT(spy_gc_alloc_mem)(size_t size);

/* Define the struct and accessor functions to represent a managed pointer to
   type T.

   The C backend emits the struct definition:
   typedef struct Ptr_T {
       T *p;
   #ifdef SPY_PTR_CHECKED
       size_t length;
   #endif
   } Ptr_T;

   SPY_PTR_FUNCTIONS(Ptr_T, T) defines all the accessor functions such as
   Ptr_T$gc_alloc, Ptr_T$load, etc.

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

#define _SPY_PTR_FUNCTIONS__UNCHECKED(PTR, T)                    \
    static inline PTR PTR##_from_addr(T *p) {                    \
        return (PTR){p};                                         \
    }                                                            \
    static inline PTR PTR##$gc_alloc(size_t n) {                 \
        spy_GcRef ref = spy_GcAlloc(sizeof(T) * n);              \
        return ( PTR ){ ref.p };                                 \
    }                                                            \
    static inline T PTR##$load(PTR p, size_t i) {                \
        return p.p[i];                                           \
    }                                                            \
    static inline void PTR##$store(PTR p, size_t i, T v) {       \
        p.p[i] = v;                                              \
    }                                                            \
    static inline bool PTR##$eq(PTR p0, PTR p1) {                \
        return p0.p == p1.p;                                     \
    }                                                            \
    static inline bool PTR##$ne(PTR p0, PTR p1) {                \
        return p0.p != p1.p;                                     \
    }                                                            \
    static inline bool PTR##$to_bool(PTR p) {                    \
        return p.p;                                              \
    }


#define _SPY_PTR_FUNCTIONS_CHECKED(PTR, T)                       \
    static inline PTR PTR##_from_addr(T *p) {                    \
        return (PTR){p, 1};                                      \
    }                                                            \
    static inline PTR PTR##$gc_alloc(size_t n) {                 \
        spy_GcRef ref = spy_GcAlloc(sizeof(T) * n);              \
        return ( PTR ){ ref.p, n };                              \
    }                                                            \
    static inline T PTR##$load(PTR p, size_t i) {                \
        if (i >= p.length)                                       \
            spy_panic("ptr_load out of bounds", __FILE__, __LINE__);    \
        return p.p[i];                                           \
    }                                                            \
    static inline void PTR##$store(PTR p, size_t i, T v) {       \
        if (i >= p.length)                                       \
            spy_panic("ptr_store ouf of bounds", __FILE__, __LINE__);   \
        p.p[i] = v;                                              \
    }                                                            \
    static inline bool PTR##$eq(PTR p0, PTR p1) {                \
        return p0.p == p1.p && p0.length == p1.length;           \
    }                                                            \
    static inline bool PTR##$ne(PTR p0, PTR p1) {                \
        return p0.p != p1.p || p0.length != p1.length;           \
    }                                                            \
    static inline bool PTR##$to_bool(PTR p) {                    \
        return p.p;                                              \
    }

#endif /* SPY_UNSAFE_H */
