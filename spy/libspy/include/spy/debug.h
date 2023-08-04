#ifndef SPY_DEBUG_H
#define SPY_DEBUG_H

#include "spy.h"

// this is a WASM import, must be provided by the host
void spy_debug_log(const char *s);

#endif /* SPY_DEBUG_H */
