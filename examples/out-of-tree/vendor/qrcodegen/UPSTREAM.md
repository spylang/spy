# Upstream

The C source files in this directory (`qrcodegen.c`, `qrcodegen.h`) are
vendored verbatim from Project Nayuki's QR Code generator library:

- Project page: https://www.nayuki.io/page/qr-code-generator-library
- GitHub repo:  https://github.com/nayuki/QR-Code-generator
- License:      MIT (see `LICENSE`)

Only the C implementation (the `c/` subdirectory of the upstream repo) is
vendored here. The `Makefile` in this directory is **not** from upstream;
it was added for this SPy example.
