# use ./make.sh -O3 to enable optimizations

LIBSPY="/home/antocuni/anaconda/spy/spy/libspy"

emcc $1 \
    -I ${LIBSPY}/include/ \
    raw_c_demo.c \
    ${LIBSPY}/src/jsffi/jsffi.c \
    -sEXPORTED_FUNCTIONS="['_main']" \
    -sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE='$dynCall' \
    -o raw_c_demo.js

emcc $1 \
    -I ${LIBSPY}/include/ \
    lldemo.c \
    ${LIBSPY}/src/jsffi/jsffi.c \
    -sEXPORTED_FUNCTIONS="['_main']" \
    -o lldemo.js


emcc $1 \
    -I ${LIBSPY}/include/ \
    demo.c \
    ${LIBSPY}/src/jsffi/jsffi.c \
    -sEXPORTED_FUNCTIONS="['_main']" \
    -o demo.js
