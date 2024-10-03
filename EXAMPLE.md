Let's make install spy and generate something we can compile with C and run.

Requires:
- Emscripten
- Zig
- Fresh Python 3.12 possibly less, but Python 3.9 doesn't suit
- gcc/clang

For Mac OS:

```bash
brew install zig && brew install emscripten
```

Build native libraries for spy:

```bash
(cd spy/libspy && make TARGET= && make TARGET=native && make TARGET=wasi)
```

Setup one example:

```
cat > examples/generics.spy << EOF
# filename: generics.spy

@blue
def make_fn(T):
  def fn(x: T, y: T) -> T:
    return x + y * 2
  return fn

fn_i32 = make_fn(i32)
fn_f64 = make_fn(f64)

def main() -> void:
  if True:
     print(fn_f64(1, 2))
  else:
     print(fn_f64(1, 3))
EOF
```

Setup spy in the virtual env:

```bash
python -m venv .venv
source .venv/bin/activate
python -m ensurepip
python -m install -r requirements.txt

python setup.py install
```

Run generation:

```bash
python -m spy examples/generics.spy

gcc -I`pwd`/spy/libspy/include -D SPY_TARGET_NATIVE \
  examples/generics.c `pwd`/spy/libspy/build/native/libspy.a

./a.out
>>> 5.000000
```