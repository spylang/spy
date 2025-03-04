# SPy Language - Dev Reference

## Common Commands
- Run all tests: `pytest`
- Run single test: `pytest spy/tests/path/to/test_file.py::TestClass::test_function`
- Run backend-specific tests: `pytest -m interp` or `-m C` or `-m doppler`
- Type checking: `mypy`
- Test shortcut: `source pytest-shortcut.sh` (enables `p` as pytest alias with tab completion)

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
- Organize imports by standard Python conventions
- Prefer specific imports: `from spy.errors import SPyError`
- Tests inherit from `CompilerTest` base class
- Use backend-specific decorators for test filtering (`@only_interp`, `@skip_backends`)