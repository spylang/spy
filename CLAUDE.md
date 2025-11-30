# SPy Language - Dev Reference

## General behavior of claude code
- when asked to write a test, write just the test without trying to fix it

## How to write comments

Avoid writing useless comments: if you need to write a comment, explain WHY the code
does something instead of WHAT it does.

Examples of USELESS comments (they just describe what the code obviously does):
```python
# Convert to py.path.local
path = py.path.local(str(path_item))

# Loop through all files
for file in files:
    ...

# Check if path is a directory
if path.check(dir=True):
    ...
```

Examples of USEFUL comments (they explain WHY or provide context):

This is USEFUL because it's not immediately obvious that `capture_output=True`
influencese also stderr:
```python
# Use capture_output=True to capture stdout and stderr separately
proc = subprocess.run(cmdline_s, capture_output=True)
```

This is USEFUL because it explains why decided to apply or not apply the conversion:
```python
if w_typeconv is None:
    # no conversion needed, hooray
    return wam
elif self.redshifting:
    # we are performing redshifting: the conversion will be handlded
    # by FuncDoppler
    return wam
else:
    # apply the conversion immediately
    w_val = self.vm.fast_call(w_typeconv, [wam.w_val])
```

This is USEFUL because by just looking at `exec_stmt` it's not immediately obvious that
we are talking about method definitions:
```python
# execute method definitions
for stmt in self.classdef.body:
    self.exec_stmt(stmt)
```

When in doubt: if the comment can be removed and the code is still clear, remove it.

## Imports

- Organize imports by standard Python conventions
- Prefer specific imports: `from spy.errors import SPyError`
- Prefer module-level imports, unless there is a good reason to put them inside functions

For example:
```python
def foo():
    # don't do this: put "import time" at the top level"
    import time
```



## Common Commands
- When running tests, always use the venv: e.g. `./venv/bin/pytest'
- Run all tests: `pytest`
- Run single test: `pytest spy/tests/path/to/test_file.py::TestClass::test_function`
- Run backend-specific tests: `pytest -m interp` or `-m C` or `-m doppler`
- Type checking: `mypy`

## Compile SPy Code
```bash
spy your_file.spy                 # Execute (default)
spy -C your_file.spy              # Generate C code
spy -c your_file.spy              # Compile to executable
spy -O 1 -g your_file.spy         # With optimization and debug symbols
```

## Code Style Guidelines
- Use strict typing (mypy enforced)
- Classes: PascalCase (`CompilerTest`)
- Functions/methods: snake_case (`compile_module()`)
- Constants: SCREAMING_SNAKE_CASE (`ALL_BACKENDS`)
- Tests inherit from `CompilerTest` base class
- Use backend-specific decorators for test filtering (`@only_interp`, `@skip_backends`)
- prefer using py.path.local over pathlib.Path. The only exception is cli.py, because
  typer has special logic to handle Path objects.
- when using triple-quoted docstrings, always put the text in its own line. E.g.:
    ```
    def foo():
        """
        docstring here
        """
    ```


## GH PR Guidelines
- When creating a PR, describe what you did, but don't include the "test plan" section.
