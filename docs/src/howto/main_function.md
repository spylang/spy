title: The Main Function
---

All SPy programs that are run in the interpreter or compiled must have a `main` function. The main function is the entry point of the program, and it is where the execution of the program begins.

```py
def main() -> None:
    print("Hello world")
```

Not every `.spy` module needs a main function, but the module invoked by, e.g. `spy foo.spy` `spy build foo.spy` must contain a main function.

Modules which are compiled as a library (e.g. `spy build --target lib foo.spy` or `--target py-cffi`) do not need a main function.

## Return Codes

The `main` function may be typed to return an `int` (`i32`). If so, the return value of the main function will be the return value of the program:

```py
#retcode.spy
def main() -> int
    return 123
```
```
$ uv run spy retcode.spy
$ echo $?
123
```


## Accessing Command Line Arguments

If the `main` function accepts a list of strings as an argument, the SPy program will accept arguments from the command line, both when running in interpreted

```py
#args.spy
def main(args: list[str]) -> None:
    print(args[1])
```
```
$ uv run spy args.spy 999
999
```

As with CPython, args[0] is the name of the string passed to the uv runtime. This is the equivalent of CPython's `sys.argv`:

```py
#argname.spy
def main(argv: list[str]) -> None:
    print(args[0])
```
```
$ uv run spy argname.spy
foo.spy
```