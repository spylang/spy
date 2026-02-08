CC := zig cc -target x86_64-linux-musl
CFLAGS := -O3

CURL_VERSION := 8.5.0
CURL_SOURCE := curl-source
CURL_STATIC := curl-static

# Paths for consumers to use
SDK_CFLAGS := -I$(CURDIR) -I$(CURDIR)/$(CURL_STATIC)/include
SDK_LDFLAGS := $(CURDIR)/aws_lambda.o -L$(CURDIR)/$(CURL_STATIC)/lib -lcurl

.PHONY: all clean curl-deps

all: aws_lambda.o

curl-deps:
	@if [ ! -d "$(CURL_STATIC)" ]; then \
		echo "Downloading libcurl $(CURL_VERSION) source..."; \
		wget -q "https://curl.se/download/curl-$(CURL_VERSION).tar.gz"; \
		tar xzf "curl-$(CURL_VERSION).tar.gz"; \
		mv "curl-$(CURL_VERSION)" $(CURL_SOURCE); \
		rm "curl-$(CURL_VERSION).tar.gz"; \
		echo "Building libcurl statically with musl..."; \
		cd $(CURL_SOURCE) && \
		CC="zig cc -target x86_64-linux-musl" \
		./configure --disable-shared --enable-static --disable-ldap --disable-sspi \
			--without-librtmp --without-libpsl --disable-ftp --disable-file \
			--disable-dict --disable-telnet --disable-tftp --disable-rtsp \
			--disable-pop3 --disable-imap --disable-smtp --disable-gopher \
			--disable-manual --without-zlib --without-ssl \
			--prefix="$$(pwd)/../$(CURL_STATIC)" && \
		make -j$$(nproc) && \
		make install; \
	fi

aws_lambda.o: aws_lambda.c aws_lambda.h curl-deps
	$(CC) $(CFLAGS) -I$(CURL_STATIC)/include -c aws_lambda.c -o aws_lambda.o

clean:
	rm -f aws_lambda.o
	rm -rf $(CURL_SOURCE) $(CURL_STATIC) curl-*.tar.gz
