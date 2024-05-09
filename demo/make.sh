# use ./make.sh -O3 to enable optimizations

LIBSPY="/home/antocuni/anaconda/spy/spy/libspy"

emcc $1 \
    -I ${LIBSPY}/include/ \
    demo.c \
    ${LIBSPY}/src/jsffi/jsffi.c \
    -sEXPORTED_FUNCTIONS="['_main']" \
    -o demo.js
