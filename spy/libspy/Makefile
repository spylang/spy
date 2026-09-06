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

SRCS = src/str.c src/bytes.c src/builtins.c src/debug.c src/unsafe.c src/operator.c src/posix.c \
       vendored/ryu/ryu/f2s.c

# Use Ryu's dedicated f32 lookup tables instead of depending on its d2s tables.
RYU_CFLAGS := -I $(CURDIR)/vendored/ryu -DRYU_FLOAT_FULL_TABLE

# Add BUILD_TYPE with a default value
BUILD_TYPE ?= release
OUTPUT_KIND ?= exe

ifeq ($(filter $(BUILD_TYPE),debug release),)
  $(error Invalid BUILD_TYPE: '$(BUILD_TYPE)'. Valid: debug, release)
endif

ifeq ($(filter $(OUTPUT_KIND),exe testlib),)
  $(error Invalid OUTPUT_KIND: '$(OUTPUT_KIND)'. Valid: exe, testlib)
endif

ifeq ($(OUTPUT_KIND), testlib)
  BUILD_DIR := build/$(TARGET)/$(BUILD_TYPE)-testlib
else
  BUILD_DIR := build/$(TARGET)/$(BUILD_TYPE)
endif

# don't bother invoking spy.build.flags if we don't have a TARGET
ifneq ($(TARGET),)
	CC             := $(shell python -m spy.build.flags --cc     --target=$(TARGET))
	AR             := $(shell python -m spy.build.flags --ar     --target=$(TARGET))
	CFLAGS         := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE) --output-kind=$(OUTPUT_KIND)) $(RYU_CFLAGS)
endif

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

# ---------- wasi target ----------
else ifeq ($(TARGET), wasi)
	LDFLAGS := \
		--no-entry \
		--import-memory

	ifeq ($(OUTPUT_KIND), testlib)
		.DEFAULT_GOAL := wasi_all_testlib
	else
		.DEFAULT_GOAL := wasi_all
	endif

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
    .DEFAULT_GOAL := emscripten_all
  endif

# ---------- native target ----------
else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := native_all

# ------- native-static target ------
else ifeq ($(TARGET), native-static)
  ifeq ($(shell uname -s),Darwin)
    $(warning Skipping native-static target - not supported on macOS)
    .DEFAULT_GOAL := skip_native_static
  else
    .DEFAULT_GOAL := native_static_all
  endif

# ---------- invalid target ---------
else
	.DEFAULT_GOAL := usage
endif

OBJS         := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

# Build all targets in release/debug mode
all:
	make TARGET=native        BUILD_TYPE=release OUTPUT_KIND=exe
	make TARGET=native        BUILD_TYPE=debug   OUTPUT_KIND=exe
	make TARGET=native-static BUILD_TYPE=release OUTPUT_KIND=exe
	make TARGET=native-static BUILD_TYPE=debug   OUTPUT_KIND=exe

	make TARGET=wasi          BUILD_TYPE=release OUTPUT_KIND=exe
	make TARGET=wasi          BUILD_TYPE=debug   OUTPUT_KIND=exe
	make TARGET=wasi          BUILD_TYPE=debug   OUTPUT_KIND=testlib

	make TARGET=emscripten    BUILD_TYPE=release OUTPUT_KIND=exe
	make TARGET=emscripten    BUILD_TYPE=debug   OUTPUT_KIND=exe
	make TARGET=emscripten    BUILD_TYPE=debug   OUTPUT_KIND=testlib

# wasi-specific rules
wasi_all_testlib: $(BUILD_DIR)/libspy.wasm
wasi_all: $(BUILD_DIR)/libspy.a

# libspy.wasm is loaded by the SPy VM, which provides the debug helpers as WASM
# imports: this is why we build it out of the testlib flavor
$(BUILD_DIR)/libspy.wasm: $(BUILD_DIR)/libspy.a
	$(CC) \
        --target=wasm32-wasi-musl \
        -mexec-model=reactor \
        -Wl,--whole-archive \
        $(BUILD_DIR)/libspy.a \
        -o $@

# emscripten-specific rules
emscripten_all: $(BUILD_DIR)/libspy.mjs

$(BUILD_DIR)/libspy.mjs: $(BUILD_DIR)/libspy.a
	$(CC) \
		$(LDFLAGS) \
        -Wl,--whole-archive \
		$(BUILD_DIR)/libspy.a \
		-o $@


$(BUILD_DIR):
	mkdir -p $@

# generic rules
native_all: $(BUILD_DIR)/libspy.a

native_static_all: $(BUILD_DIR)/libspy.a

$(BUILD_DIR)/libspy.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MMD -MF $@.d -c $< -o $@


# without this, editing a header does not trigger a recompilation, and we can
# end up with .a files whose objects were compiled with different versions of
# debug.h
-include $(OBJS:.o=.o.d)

skip_native_static:
	@echo "Skipping native-static build - not supported on macOS"

skip_emscripten:
	@echo "Skipping emscripten build - emcc compiler not found"
	@echo "To build for emscripten, please install and activate the emsdk toolchain"

clean:
	rm -rf build


usage:
	@echo "Usage: make TARGET=[wasi|emscripten|native|native-static] BUILD_TYPE=[release|debug]"
