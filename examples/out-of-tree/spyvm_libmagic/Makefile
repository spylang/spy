# Build the libmagic<->SPy glue code into a static archive.
#
# Unlike vendor/qrcodegen, libmagic is an *external system library*: we only
# build our own glue here (src/libmagic_spy.c) and let the final SPy binary
# link the system library with -lmagic. There is no WASM build of libmagic, so
# this Makefile only knows about native targets.
#
# Compiler flags are derived from spy.build.flags so that the glue stays in
# sync with libspy's own build flags.

SRCS = src/libmagic_spy.c

# libmagic's own header lives in a standard system include dir.
EXTRA_CFLAGS := -Wall -std=c99

BUILD_DIR := build/$(TARGET)

BUILD_TYPE ?= debug

ifneq ($(TARGET),)
	CC    := $(shell python -m spy.build.flags --cc  --target=$(TARGET))
	AR    := $(shell python -m spy.build.flags --ar  --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE)) $(EXTRA_CFLAGS)
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- native target ----------
else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := build/native/libmagic_spy.a

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
	$(warning Skipping native-static target - not supported on macOS)
	.DEFAULT_GOAL := skip_native_static
  else
	.DEFAULT_GOAL := build/native-static/libmagic_spy.a
  endif

# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(notdir $(SRCS)))

all:
	make TARGET=native
	make TARGET=native-static

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libmagic_spy.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

skip_native_static:
	@echo "Skipping native-static build - not supported on macOS"

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[native|native-static]"
