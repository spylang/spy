# SPy Language - Dev Reference

## Common Commands
- When running tests, always use the venv: e.g. `./venv/bin/pytest'
- Run all tests: `pytest`
- Run single test: `pytest spy/tests/path/to/test_file.py::TestClass::test_function`
- Run backend-specific tests: `pytest -m interp` or `-m C` or `-m doppler`
- Type checking: `mypy`

## Compile SPy Code
```bash
spy your_file.spy                 # Execute (default)
spy build your_file.spy           # Compile to executable
spy build -x your_file.spy        # Compile to executable AND execute
spy --help                        # To see other commands to inspect the pipeline
```

## When/how to run tests

The full test suite is slow. When you work on a feature with a limited/precise scope,
run just the tests relevant to the specific feature and/or the files that you are
modifying (use your own judgment).

When you want to run `tests/compiler` tests for a whole file and/or for the whole dir
AND the file takes many seconds to run (e.g. if it contains many tests), prefer to run
them backend-by-backend: `interp` tests are the fastest and catch most of the problems;
`doppler` tests are a bit slower and catch doppler-specific tests; `C` backend are
slowest and should be run only at the end.

So, if you decide to run all the tests for the file `test_foo.py`, do this:

1. `pytest test_foo.py -m interp`
2. `pytest test_foo.py -m doppler`
3. `pytest test_foo.py -m C`

Beware that come test files define their own "extra" backends.

If the test file is very short and it's quick to run, feel free to run with all backends
in one go.

If you modify something which is likely to impact everything, a good smoke test is
`test_basic.py`: run it in isolation before running the whole test suite.

Under normal development it is not necessary to run the full test suite before each
commit, it is fine to run it only to make sure that the branch is ready. However, if you
do whole-program modifications which are likely to break things "everywhere", then feel
free to run it more often. Use your own judgment.


## General behavior
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

- when writing tests, do NOT put a docstring to explain what the test does, especially
  if the test name is already explicit. E.g.:
  ```
  # this is BAD: the docstring is redundant
  def test_cache_preserves_symtable(self):
      """Test that symtable is preserved in cache"""
      ...

  # this is GOOD:
  def test_cache_preserves_symtable(self):
      ...
  ```

- when writing tests, don't add a new class to group new tests in an existing file,
  unless it's necessary. Prefer adding tests to the existing class. The general rule is
  one `Test*` class per `test_*.py` file.


## When to write unit tests

A unit test is worth writing only if the complexity of the thing being tested is
high enough to justify it.

A test that just mirrors a declaration or configuration is a **change-detector**,
not a safety net. If updating the code always means updating the test in lockstep,
the test adds no value — it only adds maintenance burden. Tests should verify
*behavior that emerges from the interaction of multiple pieces*, not re-state what
a single declaration says.

If the logic is trivial AND it is exercised downstream by other tests (e.g.
integration/compiler tests), it is fine to rely on those instead of writing
dedicated unit tests. For example: if you put the wrong `@astnode("...")` spec on a
node class, the compiler tests will catch it. A unit test that just asserts
`SomeNode._valid_states == frozenset({"parsed"})` adds nothing.

## GH PR Guidelines
- When creating a PR, describe what you did, but don't include the "test plan" section.
