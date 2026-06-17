# Build the qrcodegen<->SPy glue code together with the vendored qrcodegen
# library as a single static archive.
#
# Compiler flags are derived from spy.build.flags so that the glue stays in
# sync with libspy's own build flags. The glue #includes both libspy's public
# headers and the vendored qrcodegen headers.

EMCC_AVAILABLE := $(shell which emcc 2>/dev/null)

SRCS = src/spyvm_qrcodegen.c ../vendor/qrcodegen/qrcodegen.c

# qrcodegen headers, on top of the flags coming from spy.build.flags.
EXTRA_CFLAGS := -Wall -std=c99 -I../vendor/qrcodegen

BUILD_TYPE ?= debug
BUILD_DIR := build/$(TARGET)/$(BUILD_TYPE)

ifneq ($(TARGET),)
	CC    := $(shell python -m spy.build.flags --cc  --target=$(TARGET))
	AR    := $(shell python -m spy.build.flags --ar  --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE)) $(EXTRA_CFLAGS)
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	.DEFAULT_GOAL := build/wasi/$(BUILD_TYPE)/spyvm_qrcodegen.a

# -------- emscripten target --------
else ifeq ($(TARGET), emscripten)
	ifeq ($(EMCC_AVAILABLE),)
		$(warning Skipping emscripten target - emcc compiler not found in PATH)
		.DEFAULT_GOAL := skip_emscripten
	else
		.DEFAULT_GOAL := build/emscripten/$(BUILD_TYPE)/spyvm_qrcodegen.a
	endif

# ---------- native target ----------
else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := build/native/$(BUILD_TYPE)/spyvm_qrcodegen.a

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
	$(warning Skipping native-static target - not supported on macOS)
	.DEFAULT_GOAL := skip_native_static
  else
	.DEFAULT_GOAL := build/native-static/$(BUILD_TYPE)/spyvm_qrcodegen.a
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

build/$(TARGET)/$(BUILD_TYPE)/spyvm_qrcodegen.a: $(OBJS)
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
