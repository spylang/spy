# makefile to build libspy with the zig toolchian

CFLAGS=-DNDEBUG -O3 \
		-fvisibility=hidden \
		--target=wasm32-freestanding -nostdlib -Iinclude/ \
		-mmultivalue -Xclang -target-abi -Xclang experimental-mv \
		-mbulk-memory

LDFLAGS=--no-entry --import-memory

OBJECTS=vendored/walloc/walloc.o src/str.o src/builtins.o

libspy.wasm: libspy.a
	zig wasm-ld \
		--no-entry	 \
		--import-undefined \
		--whole-archive \
		libspy.a \
		-o libspy.wasm

libspy.a: $(OBJECTS)
	zig ar rcs libspy.a $(OBJECTS)

%.o: %.c
	zig cc $(CFLAGS) -c $< -o $@

clean:
	rm -f *.wasm
	rm -f *.a
	rm -f `find -name '*.o'`
