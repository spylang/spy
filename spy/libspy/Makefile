# makefile to build libspy with the zig toolchian

CFLAGS=-DNDEBUG -O3 --target=wasm32-freestanding -nostdlib
LDFLAGS=--no-entry --import-memory

OBJECTS=vendored/walloc/walloc.o

libspy.a: $(OBJECTS)
	zig ar rcs libspy.a $(OBJECTS)

%.o: %.c
	zig cc $(CFLAGS) -c $< -o $@

clean:
	rm -f *.wasm
	rm -f *.a
	rm -f `find -name '*.o'`
