# Supported targets and compilers:
#
#   TARGET         TRIPLET                     COMPILER
#   native         x86_64-pc-linux-gnu (*)     cc
#   native-static  native-native-musl          zig cc
#   wasi           wasm32-wasi-musl            zig cc
#   emscripten     wasm32-unknown-emscripten   emcc
#
# (*) the actual triplet for "native" depends on your system, of course
#
EMCC_AVAILABLE := $(shell which emcc 2>/dev/null)

SRCS = src/str.c src/bytes.c src/builtins.c src/debug.c src/unsafe.c src/operator.c src/posix.c

# Add BUILD_TYPE with a default value
BUILD_TYPE ?= release

# Modify BUILD_DIR to include build type
BUILD_DIR := build/$(TARGET)/$(BUILD_TYPE)

# don't bother invoking spy.build.flags if we don't have a TARGET
ifneq ($(TARGET),)
	CC     := $(shell python -m spy.build.flags --cc     --target=$(TARGET))
	AR     := $(shell python -m spy.build.flags --ar     --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE))
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	LDFLAGS := \
		--no-entry \
		--import-memory

	.DEFAULT_GOAL := build/wasi/$(BUILD_TYPE)/libspy.wasm

# -------- emscripten target --------
else ifeq ($(TARGET), emscripten)
	LDFLAGS := \
		-sWASM_BIGINT \
		-sEXPORTED_RUNTIME_METHODS=HEAP8

	SRCS := \
		$(SRCS) \
		src/jsffi/jsffi.c

	ifeq ($(EMCC_AVAILABLE),)
		# emcc not found - display message and skip
		$(warning Skipping emscripten target - emcc compiler not found in PATH)
		.DEFAULT_GOAL := skip_emscripten
	else
		.DEFAULT_GOAL := build/emscripten/$(BUILD_TYPE)/libspy.mjs
	endif

# ---------- native target ----------
else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := build/native/$(BUILD_TYPE)/libspy.a

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
    $(warning Skipping native-static target - not supported on macOS)
    .DEFAULT_GOAL := skip_native_static
  else
	.DEFAULT_GOAL := build/native-static/$(BUILD_TYPE)/libspy.a
  endif

# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

# Build all targets in release/debug mode
all:
	make TARGET=wasi BUILD_TYPE=release
	make TARGET=wasi BUILD_TYPE=debug
	make TARGET=native BUILD_TYPE=release
	make TARGET=native BUILD_TYPE=debug
	make TARGET=native-static BUILD_TYPE=release
	make TARGET=native-static BUILD_TYPE=debug
	make TARGET=emscripten BUILD_TYPE=release
	make TARGET=emscripten BUILD_TYPE=debug

# wasi-specific rules
build/wasi/$(BUILD_TYPE)/libspy.wasm: build/$(TARGET)/$(BUILD_TYPE)/libspy.a
	$(CC) \
        --target=wasm32-wasi-musl \
        -mexec-model=reactor \
        -Wl,--whole-archive \
        build/$(TARGET)/$(BUILD_TYPE)/libspy.a \
        -o $@

# emscripten-specific rules
build/emscripten/$(BUILD_TYPE)/libspy.mjs: build/$(TARGET)/$(BUILD_TYPE)/libspy.a
	$(CC) \
		$(LDFLAGS) \
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

skip_native_static:
	@echo "Skipping native-static build - not supported on macOS"

skip_emscripten:
	@echo "Skipping emscripten build - emcc compiler not found"
	@echo "To build for emscripten, please install and activate the emsdk toolchain"

clean:
	rm -rf build


usage:
	@echo "Usage: make TARGET=[wasi|emscripten|native|native-static] BUILD_TYPE=[release|debug]"
