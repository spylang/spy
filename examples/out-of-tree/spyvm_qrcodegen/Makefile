# Build the qrcodegen<->SPy glue code together with the vendored qrcodegen
# library as a single static archive.
#
# Compiler flags are derived from spy.libspy.flags so that the glue stays in
# sync with libspy's own build flags. The glue #includes both libspy's public
# headers and the vendored qrcodegen headers.

EMCC_AVAILABLE := $(shell which emcc 2>/dev/null)

SRCS = src/qrcodegen_spy.c ../vendor/qrcodegen/qrcodegen.c

# qrcodegen headers, on top of the flags coming from spy.libspy.flags.
# SPY_DEBUG must match the build type of the libspy archive we are bundled
# with (the prebuilt libspy.wasm is a debug build); it affects struct layouts.
EXTRA_CFLAGS := -Wall -std=c99 -DSPY_DEBUG -O0 -g -I../vendor/qrcodegen

BUILD_DIR := build/$(TARGET)

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	CC    := $(shell python -m spy.libspy.flags --cc  --target=wasi)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=wasi)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=wasi) $(EXTRA_CFLAGS)
	.DEFAULT_GOAL := build/wasi/libqrcodegen_spy.a

# -------- emscripten target --------
else ifeq ($(TARGET), emscripten)
	CC    := $(shell python -m spy.libspy.flags --cc  --target=emscripten)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=emscripten)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=emscripten) $(EXTRA_CFLAGS)
	ifeq ($(EMCC_AVAILABLE),)
		$(warning Skipping emscripten target - emcc compiler not found in PATH)
		.DEFAULT_GOAL := skip_emscripten
	else
		.DEFAULT_GOAL := build/emscripten/libqrcodegen_spy.a
	endif

# ---------- native target ----------
else ifeq ($(TARGET), native)
	CC    := $(shell python -m spy.libspy.flags --cc  --target=native)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=native)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=native) $(EXTRA_CFLAGS)
	.DEFAULT_GOAL := build/native/libqrcodegen_spy.a

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
	$(warning Skipping native-static target - not supported on macOS)
	.DEFAULT_GOAL := skip_native_static
  else
	CC    := $(shell python -m spy.libspy.flags --cc  --target=native-static)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=native-static)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=native-static) $(EXTRA_CFLAGS)
	.DEFAULT_GOAL := build/native-static/libqrcodegen_spy.a
  endif

# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(notdir $(SRCS)))

all:
	make TARGET=wasi
	make TARGET=native
	make TARGET=native-static
	make TARGET=emscripten

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libqrcodegen_spy.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: ../vendor/qrcodegen/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

skip_native_static:
	@echo "Skipping native-static build - not supported on macOS"

skip_emscripten:
	@echo "Skipping emscripten build - emcc compiler not found"

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[wasi|emscripten|native|native-static]"
