SPy CFFI demo
==============

This is a simple example which shows how to convert a .spy into a CPython C
extension.

If you select the `py-cffi` "output kind", `spy` generates the following:

  - `./build/cffi/_spydemo.cffi-build.py`: CFFI bindings
  - `./build/cffi/spydemo.py`: Pythonic interface on top of `_spydemo`.


There are two ways to generate the extension:

1. by letting `spy` to invoke the C compiler for you:
   ```
   $ spy --output-kind py-cffi --compile spydemo.spy
   ==> build/cffi/_spydemo.cpython-312-x86_64-linux-gnu.so
   ```

2. by letting `spy` to generated only the source code, and then use `setup.py`
   to do actual compilation:
   ```
   $ spy --output-kind py-cffi --cwrite spydemo.spy
   C files:      build/src/spydemo.c
   Build script: build/cffi/_spydemo-cffi-build.py

   $ python setup.py build
   ```

XXX: `python -m build` doesn't work. PRs to fix it are welcome :).
