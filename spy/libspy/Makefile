# Supported targets and compilers:
#
#   TARGET      TRIPLET                     COMPILER
#   wasi        wasm32-wasi-musl            zig cc
#   emscripten  wasm32-unknown-emscripten   emcc
#   native      x86_64-pc-linux-gnu (*)     cc
#
# (*) the actual triplet for "native" depends on your system, of course

SRCS = src/str.c src/builtins.c src/debug.c

CFLAGS := \
	-DNDEBUG -O3 \
	-fvisibility=hidden \
	-Iinclude

# uncomment to enable debugging
#CFLAGS := $(CFLAGS) -O0 -g

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	CC := zig cc
	LD := zig wasm-ld
	AR := zig ar

	CFLAGS := \
		$(CFLAGS) \
		-DSPY_TARGET_WASI \
		--target=wasm32-wasi-musl \
		-mmultivalue \
		-Xclang -target-abi \
		-Xclang experimental-mv \
		-mbulk-memory

	LDFLAGS := \
		--no-entry \
		--import-memory

	.DEFAULT_GOAL := build/wasi/libspy.wasm

# -------- emscripten target --------
else ifeq ($(TARGET), emscripten)
	CC := emcc
	AR := emar

	CFLAGS := \
		$(CFLAGS) \
		-DSPY_TARGET_EMSCRIPTEN \
		-mmultivalue \
		-Xclang -target-abi \
		-Xclang experimental-mv \
		-mbulk-memory

	SRCS := \
		$(SRCS) \
		src/jsffi/jsffi.c

	.DEFAULT_GOAL = build/emscripten/libspy.a

# ---------- native target ----------
else ifeq ($(TARGET), native)
	CC := cc
	LD := ld
	AR := ar

	CFLAGS := \
		$(CFLAGS) \
		-DSPY_TARGET_NATIVE

	.DEFAULT_GOAL := build/native/libspy.a


# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

BUILD_DIR := build/$(TARGET)
OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

all:
	make TARGET=wasi
	make TARGET=emscripten
	make TARGET=native

build/wasi/libspy.wasm: build/$(TARGET)/libspy.a
	$(CC) \
		--target=wasm32-wasi-musl \
		-mexec-model=reactor \
		-Wl,--whole-archive \
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
	@echo "Usage: make TARGET=[wasi|emscripten|native]"
