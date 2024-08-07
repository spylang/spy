set -e

# use ./make.sh -O3 to enable optimizations

LIBSPY="/home/antocuni/anaconda/spy/spy/libspy"

CFLAGS="
  $1
  -D SPY_TARGET_EMSCRIPTEN
  -I ${LIBSPY}/include/
  -L ${LIBSPY}/build/emscripten/
  -lspy
"


emcc $CFLAGS raw_c_demo.c -o raw_c_demo.js

# ../spy.sh --cwrite lldemo.spy
# emcc $CFLAGS lldemo.c -o lldemo.js
../../spy.sh -t emscripten lldemo.spy

# ../spy.sh --cwrite demo.spy
# emcc $CFLAGS demo.c -o demo.js
../../spy.sh -t emscripten demo.spy
