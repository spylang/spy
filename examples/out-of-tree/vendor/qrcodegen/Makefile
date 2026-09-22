# Build qrcodegen as a static library, using the same compilers/targets as
# libspy (see spy/libspy/Makefile). Supported targets:
#
#   TARGET         TRIPLET                     COMPILER
#   native         x86_64-pc-linux-gnu (*)     cc
#   native-static  native-native-musl          zig cc
#   wasi           wasm32-wasi-musl            zig cc
#   emscripten     wasm32-unknown-emscripten   emcc
#
# In a real-world setup, the user would install qrcodegen via the system
# package manager (apt/brew/...) or via a language-specific package manager.
# Here we vendor the upstream source for self-containment.
#
# Compiler flags are derived from spy.build.flags so that out-of-tree
# modules always stay in sync with libspy's own build flags.

EMCC_AVAILABLE := $(shell which emcc 2>/dev/null)

SRCS = qrcodegen.c

# Extra flags specific to this library (not from spy.build.flags)
EXTRA_CFLAGS := -Wall -std=c99 -DNDEBUG -O3

BUILD_DIR := build/$(TARGET)

ifneq ($(TARGET),)
	CC    := $(shell python -m spy.build.flags --cc  --target=$(TARGET))
	AR    := $(shell python -m spy.build.flags --ar  --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET)) $(EXTRA_CFLAGS)
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	.DEFAULT_GOAL := build/wasi/libqrcodegen.a

# -------- emscripten target --------
else ifeq ($(TARGET), emscripten)
	ifeq ($(EMCC_AVAILABLE),)
		$(warning Skipping emscripten target - emcc compiler not found in PATH)
		.DEFAULT_GOAL := skip_emscripten
	else
		.DEFAULT_GOAL := build/emscripten/libqrcodegen.a
	endif

# ---------- native target ----------
else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := build/native/libqrcodegen.a

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
	$(warning Skipping native-static target - not supported on macOS)
	.DEFAULT_GOAL := skip_native_static
  else
	.DEFAULT_GOAL := build/native-static/libqrcodegen.a
  endif

# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

all:
	make TARGET=wasi
	make TARGET=native
	make TARGET=native-static
	make TARGET=emscripten

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libqrcodegen.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

skip_native_static:
	@echo "Skipping native-static build - not supported on macOS"

skip_emscripten:
	@echo "Skipping emscripten build - emcc compiler not found"
	@echo "To build for emscripten, please install and activate the emsdk toolchain"

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[wasi|emscripten|native|native-static]"
