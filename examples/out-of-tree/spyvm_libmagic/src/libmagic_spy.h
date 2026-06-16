#ifndef LIBMAGIC_SPY_H
#define LIBMAGIC_SPY_H

#include <spy.h>
#include <spy/bytes.h>
#include <spy/str.h>

spy_StrObject *spy_magic$describe(spy_BytesObject *data);
spy_StrObject *spy_magic$mime(spy_BytesObject *data);

#endif /* LIBMAGIC_SPY_H */
