# Makefile for building SPy's external dependencies.
#
# Currently supported:
#   - bdwgc (Boehm-Demers-Weiser GC) for TARGET=native-static
#
# Usage:
#   make TARGET=native-static bdwgc

BDWGC_VERSION := 8.2.8
BDWGC_TARBALL := gc-$(BDWGC_VERSION).tar.gz
BDWGC_URL := https://github.com/ivmai/bdwgc/releases/download/v$(BDWGC_VERSION)/$(BDWGC_TARBALL)
BDWGC_SRCDIR := gc-$(BDWGC_VERSION)

ZIG := $(shell python ../../getzig.py)

# --------- target-specific config ----------
ifeq ($(TARGET), native-static)
  CC_CMD := $(ZIG) cc --target=native-native-musl
  AR_CMD := $(ZIG) ar
  RANLIB_CMD := $(ZIG) ranlib
  BUILD_DIR := $(CURDIR)/build/native-static
else ifneq ($(MAKECMDGOALS),clean)
  ifneq ($(MAKECMDGOALS),distclean)
    $(error Unsupported TARGET=$(TARGET). Only native-static is supported.)
  endif
endif

.PHONY: bdwgc clean distclean

bdwgc: $(BUILD_DIR)/lib/libgc.a

# --- download ---
$(BDWGC_TARBALL):
	curl -L -o $@ $(BDWGC_URL)

# --- extract ---
$(BDWGC_SRCDIR)/configure: $(BDWGC_TARBALL)
	tar xzf $<
	touch $@

# --- build & install ---
$(BUILD_DIR)/lib/libgc.a: $(BDWGC_SRCDIR)/configure
	cd $(BDWGC_SRCDIR) && \
		./configure \
			CC="$(CC_CMD)" \
			AR="$(AR_CMD)" \
			RANLIB="$(RANLIB_CMD)" \
			--disable-shared \
			--enable-static \
			--disable-threads \
			--prefix="$(BUILD_DIR)" && \
		$(MAKE) -j$$(nproc) && \
		$(MAKE) install

clean:
	rm -rf build $(BDWGC_SRCDIR)

distclean: clean
	rm -f $(BDWGC_TARBALL)
