#ifndef SPYVM_LIBMAGIC_H
#define SPYVM_LIBMAGIC_H

#include <spy.h>
#include <spy/bytes.h>
#include <spy/str.h>

spy_StrObject *spy_magic$describe(spy_BytesObject *data);
spy_StrObject *spy_magic$mime(spy_BytesObject *data);

#endif /* SPYVM_LIBMAGIC_H */
