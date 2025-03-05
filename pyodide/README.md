# Pyodide support files

This directory contains support files for pyodide-related tests.

## Install pyodide npm package

```
$ cd /path/to/spy/pyodide/
$ npm install
```

This is needed by `test_llwasm.py`, which uses `@run_in_pyodide`. See also the
`--dist-dir` pytest option which is automatically added by
`[tool.pytest.ini_options]` in pyproject.toml.


## Install pyodide virtualenv

This is needed by `test_cli::test_execute_pyodide`.

You need the `pyodide` command, which you can get by `pip install pyodide-py`
(which is already listed as a dependency in pyproject.toml).

```
# create a pyodide venv
$ cd /path/to/spy/pyodide/
$ pyodide venv venv

# check that it works
$ ./venv/bin/python -c 'import sys; print(sys.platform)'
emscripten

# install spy in the pyodide venv
# XXX this doesn't work, see below
$ ./venv/bin/pip install -e ..
```

**WARNING**: at the moment of writing the last step doesn't work out of the
box, because of this issue: https://github.com/pyodide/pyodide/issues/5491
You can fix it by manually modifying `pip` as described in the issue above.

Once `spy` is installed, you can run spy under pyodide-node like this:

```
$ ./venv/bin/python -m spy ../examples/hello.spy
```

## Install emsdk

`llwasm/emscripten.py` doesn't work on official emscripten, because it relieas
on the `adjustWasmImports` feature which is present only in pyodide's fork of
emsdk. See also https://github.com/emscripten-core/emscripten/pull/23794

You need to install https://github.com/pyodide/pyodide/tree/main/emsdk
