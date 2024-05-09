emcc jsffi.c -o jsffi.js \
	 -sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE=['$UTF8ToString']
