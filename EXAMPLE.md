Let's make install spy and generate something we can compile with C and run.

Requires:
- Emscripten
- Python 3.10+
- gcc/clang

For Mac OS (brew):

```bash
$ brew install emscripten
```

Or please follow the recommended [installation process](https://emscripten.org/docs/getting_started/downloads.html#installation-instructions-using-the-emsdk-recommended).

Setup spy in the virtual env:

```bash
$ python -m venv venv
$ source venv/bin/activate
$ python -m ensurepip
$ python -m pip install -r requirements.txt
```

Ensure that the zig binary is available:

```bash
$ ln -s $(realpath venv/lib/python3.*/site-packages/ziglang/zig) venv/bin/
```

Build native libraries for spy:

```bash
$ make -C spy/libspy
```

Run `hello.spy` script in interpreted mode:

```bash
$ ./spy.sh --run examples/hello.spy
```

Compile to an executable:

```bash
$ ./spy.sh -t native examples/hello.spy
$ ./examples/hello
Hello world!
```

Show the AST:

```bash
$ ./spy.sh --parse examples/hello.spy
```

See what happens after redshifting:

```bash
$ ./spy.sh --redshift --no-pretty examples/hello.spy
def main() -> `builtins::void`:
    `builtins::print_str`('Hello world!')
```

Also let's try more complex case with integer typing.

```bash
$ ./spy.sh --redshift examples/generics.spy
def fn_i32(x: i32, y: i32) -> i32:
    return x + y * 2

def fn_f64(x: f64, y: f64) -> f64:
    return x + y * 2

def main() -> void:
    if True:
        print_f64(`generics::fn_f64`(1, 2))
    else:
        print_f64(`generics::fn_f64`(1, 3))
```

Same as above with `--no-pretty` making more evident some of the underlying structures:

```bash
$ ./spy.sh --redshift --no-pretty examples/generics.spy
def fn_i32(x: `builtins::i32`, y: `builtins::i32`) -> `builtins::i32`:
    return `operator::i32_add`(x, `operator::i32_mul`(y, 2))

def fn_f64(x: `builtins::f64`, y: `builtins::f64`) -> `builtins::f64`:
    return `operator::f64_add`(x, `operator::f64_mul`(y, 2))

def main() -> `builtins::void`:
    if True:
        `builtins::print_f64`(`generics::fn_f64`(1, 2))
    else:
        `builtins::print_f64`(`generics::fn_f64`(1, 3))
```