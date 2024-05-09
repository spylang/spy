LIBSPY="/home/antocuni/anaconda/spy/spy/libspy"

emcc \
    -I ${LIBSPY}/include/ \
    demo.c \
    ${LIBSPY}/src/jsffi/jsffi.c \
    -sEXPORTED_FUNCTIONS="['_main']" \
    -o demo.js
