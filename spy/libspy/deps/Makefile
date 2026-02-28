# Makefile for building SPy's external dependencies.
#
# Currently supported:
#   - bdwgc (Boehm-Demers-Weiser GC) for TARGET=native-static
#   - libcurl (HTTP client library) for TARGET=native-static
#   - aws_sdk (AWS Lambda runtime SDK) for TARGET=native-static
#
# Usage:
#   make TARGET=native-static bdwgc
#   make TARGET=native-static libcurl
#   make TARGET=native-static aws_sdk

BDWGC_VERSION := 8.2.8
BDWGC_TARBALL := gc-$(BDWGC_VERSION).tar.gz
BDWGC_URL := https://github.com/ivmai/bdwgc/releases/download/v$(BDWGC_VERSION)/$(BDWGC_TARBALL)
BDWGC_SRCDIR := gc-$(BDWGC_VERSION)

CURL_VERSION := 8.5.0
CURL_TARBALL := curl-$(CURL_VERSION).tar.gz
CURL_URL := https://github.com/curl/curl/releases/download/curl-8_5_0/$(CURL_TARBALL)
CURL_SRCDIR := curl-$(CURL_VERSION)

AWS_SDK_SRCDIR := aws_lambda_sdk

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

.PHONY: bdwgc libcurl aws_sdk clean distclean

# ==================== bdwgc ====================

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

# ==================== libcurl ====================

libcurl: $(BUILD_DIR)/lib/libcurl.a

$(CURL_TARBALL):
	curl -L -o $@ $(CURL_URL)

$(CURL_SRCDIR)/configure: $(CURL_TARBALL)
	tar xzf $<
	touch $@

$(BUILD_DIR)/lib/libcurl.a: $(CURL_SRCDIR)/configure
	cd $(CURL_SRCDIR) && \
		./configure \
			CC="$(CC_CMD)" \
			AR="$(AR_CMD)" \
			RANLIB="$(RANLIB_CMD)" \
			--disable-shared \
			--enable-static \
			--disable-ldap \
			--disable-sspi \
			--without-librtmp \
			--without-libpsl \
			--disable-ftp \
			--disable-file \
			--disable-dict \
			--disable-telnet \
			--disable-tftp \
			--disable-rtsp \
			--disable-pop3 \
			--disable-imap \
			--disable-smtp \
			--disable-gopher \
			--disable-manual \
			--without-zlib \
			--without-ssl \
			--prefix="$(BUILD_DIR)" && \
		$(MAKE) -j$$(nproc) && \
		$(MAKE) install

# ==================== aws_sdk ====================

aws_sdk: $(BUILD_DIR)/lib/libaws_lambda.a

$(BUILD_DIR)/lib/libaws_lambda.a: $(BUILD_DIR)/lib/libcurl.a $(AWS_SDK_SRCDIR)/aws_lambda.c $(AWS_SDK_SRCDIR)/aws_lambda.h
	mkdir -p $(BUILD_DIR)/lib $(BUILD_DIR)/include
	$(CC_CMD) -O3 -I$(BUILD_DIR)/include -c $(AWS_SDK_SRCDIR)/aws_lambda.c -o $(BUILD_DIR)/aws_lambda.o
	$(AR_CMD) rcs $@ $(BUILD_DIR)/aws_lambda.o
	cp $(AWS_SDK_SRCDIR)/aws_lambda.h $(BUILD_DIR)/include/
	rm -f $(BUILD_DIR)/aws_lambda.o

# ==================== clean ====================

clean:
	rm -rf build $(BDWGC_SRCDIR) $(CURL_SRCDIR)

distclean: clean
	rm -f $(BDWGC_TARBALL) $(CURL_TARBALL)
