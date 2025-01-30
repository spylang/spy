# Supported targets and compilers:
#
#   TARGET      TRIPLET                     COMPILER
#   wasi        wasm32-wasi-musl            zig cc
#   emscripten  wasm32-unknown-emscripten   emcc
#   native      x86_64-pc-linux-gnu (*)     cc
#
# (*) the actual triplet for "native" depends on your system, of course

ZIG := $(shell python ../getzig.py)
# exit early if zig can't be found
ifeq ($(ZIG),)
    $(error zig not found)
endif

SRCS = src/str.c src/builtins.c src/debug.c src/unsafe.c

# Base CFLAGS without optimization or debug settings
CFLAGS := \
    -fvisibility=hidden \
    -Iinclude

# uncomment to enable debugging
#CFLAGS := $(CFLAGS) -O0 -g

# Add BUILD_TYPE with a default value
BUILD_TYPE ?= release

# Modify BUILD_DIR to include build type
BUILD_DIR := build/$(TARGET)/$(BUILD_TYPE)

# Add build type specific flags
ifeq ($(BUILD_TYPE),release)
    CFLAGS += -DNDEBUG -DSPY_RELEASE -O3
else ifeq ($(BUILD_TYPE),debug)
    CFLAGS += -DSPY_DEBUG -O0 -g
else
    $(error Invalid BUILD_TYPE: $(BUILD_TYPE). Must be 'release' or 'debug')
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	CC := $(ZIG) cc
	LD := $(ZIG) wasm-ld
	AR := $(ZIG) ar

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

	.DEFAULT_GOAL := build/wasi/$(BUILD_TYPE)/libspy.wasm

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

	.DEFAULT_GOAL = build/emscripten/$(BUILD_TYPE)/libspy.a

# ---------- native target ----------
else ifeq ($(TARGET), native)
	CC := cc
	LD := ld
	AR := ar

	CFLAGS := \
		$(CFLAGS) \
		-DSPY_TARGET_NATIVE

	.DEFAULT_GOAL := build/native/$(BUILD_TYPE)/libspy.a


# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

# Build all targets in release/debug mode
all:
	make TARGET=wasi BUILD_TYPE=release
	make TARGET=wasi BUILD_TYPE=debug
	make TARGET=emscripten BUILD_TYPE=release
	make TARGET=emscripten BUILD_TYPE=debug
	make TARGET=native BUILD_TYPE=release
	make TARGET=native BUILD_TYPE=debug

# wasi-specific rules
build/wasi/$(BUILD_TYPE)/libspy.wasm: build/$(TARGET)/$(BUILD_TYPE)/libspy.a
	$(CC) \
        --target=wasm32-wasi-musl \
        -mexec-model=reactor \
        -Wl,--whole-archive \
        build/$(TARGET)/$(BUILD_TYPE)/libspy.a \
        -o $@

$(BUILD_DIR):
	mkdir -p $@

# generic rules
build/$(TARGET)/$(BUILD_TYPE)/libspy.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf build


usage:
	@echo "Usage: make TARGET=[wasi|emscripten|native] BUILD_TYPE=[release|debug]"
