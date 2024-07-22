# use ./make.sh -O3 to enable optimizations

LIBSPY="/home/antocuni/anaconda/spy/spy/libspy"

CFLAGS="
  $1
  -I ${LIBSPY}/include/
  ${LIBSPY}/src/jsffi/jsffi.c
  ${LIBSPY}/src/str.c
  -sEXPORTED_FUNCTIONS="['_main']"
  -sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE='\$dynCall'
  ${LIBSPY}/src/emcompat.c
"


emcc $CFLAGS raw_c_demo.c -o raw_c_demo.js
emcc $CFLAGS lldemo.c -o lldemo.js
emcc $CFLAGS demo.c -o demo.js
