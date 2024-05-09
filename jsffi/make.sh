emcc jsffi.c -o jsffi.js \
	 -sEXPORTED_FUNCTIONS="['_foo']" \
	 -sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE=['$UTF8ToString']
