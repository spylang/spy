# <ai>Build the CUI <-> SPy glue.
#
#   make            builds the native static archives (debug + release) used
#                   by the C backend, and the shared library used by the
#                   interpreter through ctypes.
#   make interp     only the shared library.
#
# CUI is fetched into vendor/CUI on first use (it is not vendored in the SPy
# repository) and its single-file distribution is generated into
# build/amalgamation. Compiler flags come from spy.build.flags so that the
# glue stays in sync with libspy.</ai>

CUI_DIR ?= vendor/CUI
AMALG   := build/amalgamation
CUI_C   := $(AMALG)/cui.c
LIBSPY_INC := $(shell python -c "import spy; print(spy.ROOT.join('libspy','include'))")

BUILD_TYPE ?= debug
BUILD_DIR  := build/$(TARGET)/$(BUILD_TYPE)

# ------- no target specified -------
ifeq ($(TARGET),)
	.DEFAULT_GOAL := all

all: native interp

native:
	make TARGET=native BUILD_TYPE=debug
	make TARGET=native BUILD_TYPE=release

interp:
	$(MAKE) build/interp/libspyvm_cui.so

$(CUI_C):
	@test -d $(CUI_DIR) || git clone --depth 1 https://github.com/yappologistic/CUI.git $(CUI_DIR)
	python3 $(CUI_DIR)/tools/amalgamate.py $(AMALG)

# ---------- native static archive (C backend) ----------
else
	CC     := $(shell python -m spy.build.flags --cc     --target=$(TARGET))
	AR     := $(shell python -m spy.build.flags --ar     --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE))
	EXTRA_CFLAGS := -std=c99 -O2 -I $(AMALG) -I src

	.DEFAULT_GOAL := build/$(TARGET)/$(BUILD_TYPE)/libspyvm_cui.a

build/$(TARGET)/$(BUILD_TYPE)/libspyvm_cui.a: $(BUILD_DIR)/cui.o $(BUILD_DIR)/spyvm_cui.o
	$(AR) rcs $@ $^

$(BUILD_DIR)/cui.o: $(CUI_C) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(EXTRA_CFLAGS) -c $(CUI_C) -o $@

$(BUILD_DIR)/spyvm_cui.o: src/spyvm_cui.c src/spyvm_cui.h $(CUI_C) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(EXTRA_CFLAGS) -c src/spyvm_cui.c -o $@

$(BUILD_DIR):
	mkdir -p $@
endif

# ---------- shared library (ctypes interpreter) ----------
build/interp/libspyvm_cui.so: src/spyvm_cui.c src/spyvm_cui.h $(CUI_C)
	mkdir -p $(dir $@)
	$(CC_NATIVE) -std=c99 -O2 -fPIC -shared \
	    -DSPYVM_CUI_CTYPES_ONLY \
	    -DSPY_TARGET_NATIVE -DSPY_RELEASE -DSPY_GC_NONE -DSPY_OUTPUT_KIND_EXE \
	    -I $(AMALG) -I src -I $(LIBSPY_INC) \
	    $(CUI_C) src/spyvm_cui.c \
	    -lX11 -ldl -lpthread -lm -o $@

CC_NATIVE ?= cc

clean:
	rm -rf build

.PHONY: all native interp clean
