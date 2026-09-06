Ryu floating-point conversion
=============================

Upstream: https://github.com/ulfjack/ryu
Revision: 4c0618b0e44f7ef027ebae05d2cc7812048f7c8f
Paper: Ulf Adams, "Ryū: Fast Float-to-String Conversion"
       https://dl.acm.org/doi/10.1145/3296979.3192369

The files in this directory are an unmodified subset of upstream Ryu. They are
used for shortest-round-trip conversion of IEEE-754 binary32 values. The
`RYU_FLOAT_FULL_TABLE` configuration requires only the dedicated f32 table and
avoids pulling in the d2s tables before SPy adds binary64 support.

Vendored files
--------------

- LICENSE-Apache2
- LICENSE-Boost
- ryu/common.h
- ryu/digit_table.h
- ryu/f2s.c
- ryu/f2s_full_table.h
- ryu/f2s_intrinsics.h
- ryu/ryu.h

License
-------

Upstream offers the files in `ryu/` under either Apache License 2.0 or Boost
Software License 1.0. Both upstream license files are included unchanged.

Updating
--------

Download the archive for the desired pinned revision, copy the files listed
above without reformatting them, update the revision in this file, and verify
that each copied file is byte-for-byte identical to upstream. If the dependency
set changes, update the file list and explain why.
