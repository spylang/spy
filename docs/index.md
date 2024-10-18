# Build Guide for Linux

## Prerequisite

- `python >= 3.10`
- `emscripten`
- `gcc`
- `git`

## Install `emscripten`

=== "Linux"
    - Get the `emsdk` repository
    ```
    git clone https://github.com/emscripten-core/emsdk.git
    ```

    - Enter `emsdk` directory
    ```
    cd emsdk
    ```

    - Make the "latest" SDK "active" for the current user (writes .emscripten file)
    ```
    ./emsdk activate latest
    ```

    - Download and install the latest SDK tools
    ```
    ./emsdk install latest
    ```

    - Activate PATH and other environment variables in the current terminal
    ```
    source ./emsdk_env.sh
    ```

=== "MacOS"
    - Install with `brew`
    ```
    $ brew install emscripten
    ```
???+ info
    Or follow the recommended [installation process](https://emscripten.org/docs/getting_started/downloads.html#installation-instructions-using-the-emsdk-recommended).

## Install `spylang`

- Get the `spylang` repository
```
git clone https://github.com/spylang/spy.git
```

- Enter `spy` directory
```
cd spy
```

- Make virtual environment for `spylang` project
```
python -m venv .venv
```

- Activate virtual environment
```
.venv/bin/activate
```

- Install `requirement.txt` for depedency
```
pip install -r requirements.txt
```

- Ensure that the `zig` is available on PATH
```
ln -s $(realpath .venv/lib/python3.*/site-packages/ziglang/zig) .venv/bin/
```

- Build native libraries for spy
```
make -C spy/libspy
```

## Basic Commands

- Execute script in interpreted mode
```
$ ./spy.sh --run examples/hello.spy 
Hello world!
```

- Compile script to an executable
```
$ ./spy.sh -t native examples/hello.spy
$ ./examples/hello
Hello world!
```

- redshifting mode
```
$ ./spy.sh --redshift --no-pretty examples/hello.spy 
def main() -> `builtins::void`:
    `builtins::print_str`('Hello world!')
```

- Run tests
```
$ pytest
```
