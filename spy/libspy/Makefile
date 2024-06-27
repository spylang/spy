# Supported targets and compilers:
#
#   TARGET      TRIPLET                     COMPILER
#   wasm32      wasm32-freestanding         zig cc
#   emscripten  wasm32-unknown-emscripten   emcc
#   native      x86_64-pc-linux-gnu (*)     cc
#
# (*) the actual triplet for "native" depends on your system, of course

SRCS = vendored/walloc/walloc.c src/libc.c src/str.c src/builtins.c

ifeq ($(TARGET),)
	.DEFAULT_GOAL := all
else ifeq ($(TARGET), wasm32)
	CFLAGS := \
		-DNDEBUG -O3 \
		-fvisibility=hidden \
		--target=wasm32-freestanding -nostdlib -Iinclude/ \
		-mmultivalue -Xclang -target-abi -Xclang experimental-mv \
		-mbulk-memory

	LDFLAGS := \
		--no-entry \
		--import-memory

	.DEFAULT_GOAL = build/wasm32/libspy.wasm
else
	.DEFAULT_GOAL := usage
endif

BUILD_DIR := build/$(TARGET)
OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

all:
	make TARGET=wasm32

build/wasm32/libspy.wasm: build/$(TARGET)/libspy.a
	zig wasm-ld \
		--no-entry	 \
		--import-undefined \
		--whole-archive \
		build/$(TARGET)/libspy.a \
		-o $@

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libspy.a: $(OBJS)
	zig ar rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	mkdir -p $(dir $@)
	zig cc $(CFLAGS) -c $< -o $@

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[wasm32|emscripten|native]"
