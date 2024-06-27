# Supported targets and compilers:
#
#   TARGET      TRIPLET                     COMPILER
#   wasm32      wasm32-freestanding         zig cc
#   emscripten  wasm32-unknown-emscripten   emcc
#   native      x86_64-pc-linux-gnu (*)     cc
#
# (*) the actual triplet for "native" depends on your system, of course

SRCS = src/str.c src/builtins.c

CFLAGS := \
	-DNDEBUG -O3 \
	-fvisibility=hidden \
	-Iinclude

# uncomment to enable debugging
#CFLAGS := $(CFLAGS) -O0 -g

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasm32 target ----------
else ifeq ($(TARGET), wasm32)
	CC := zig cc
	LD := zig wasm-ld
	AR := zig ar

	CFLAGS := \
		$(CFLAGS) \
		--target=wasm32-freestanding \
		-nostdlib  \
		-mmultivalue \
		-Xclang -target-abi \
		-Xclang experimental-mv \
		-mbulk-memory

	LDFLAGS := \
		--no-entry \
		--import-memory

	SRCS := \
		$(SRCS) \
		vendored/walloc/walloc.c \
		src/libc.c

	.DEFAULT_GOAL := build/wasm32/libspy.wasm

# ---------- native target ----------
else ifeq ($(TARGET), native)
	CC := cc
	LD := ld
	AR := ar

	.DEFAULT_GOAL := build/native/libspy.a


# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

BUILD_DIR := build/$(TARGET)
OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

all:
	make TARGET=wasm32
	make TARGET=native

build/wasm32/libspy.wasm: build/$(TARGET)/libspy.a
	$(LD) \
		--no-entry \
		--import-undefined \
		--whole-archive \
		build/$(TARGET)/libspy.a \
		-o $@

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libspy.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[wasm32|emscripten|native]"
