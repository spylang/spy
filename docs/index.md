# Build Guide for Linux

## Prerequisite

- `python >= 3.10`
- `zig >= 0.13.0`
- `emscripten`
- `gcc`
- `git`

## Install `emscripten`

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
python -m venv .venv --prompt spy
```

- Activate virtual environment
```
.venv/bin/activate
```

- Install `requirement.txt` for depedency
```
pip install -r requirements.txt
```

- Add `zig` compiler to PATH
```
ln -s $(realpath .venv/lib/python3.*/site-packages/ziglang/zig) .venv/bin/
```

- Build `libspy`
```
make -C spy/libspy
```

- Install `requirement.txt` for depedency
```
pip install -r requirements.txt
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
