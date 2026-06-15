SRCS = mymod.c

BUILD_DIR := build/$(TARGET)

BUILD_TYPE ?= debug

ifneq ($(TARGET),)
	CC    := $(shell python -m spy.build.flags --cc  --target=$(TARGET))
	AR    := $(shell python -m spy.build.flags --ar  --target=$(TARGET))
	CFLAGS := $(shell python -m spy.build.flags --cflags --target=$(TARGET) --build-type=$(BUILD_TYPE))
endif

ifeq ($(TARGET),)
	.DEFAULT_GOAL := usage

else ifeq ($(TARGET), wasi)
	.DEFAULT_GOAL := build/wasi/libmymod.a

else ifeq ($(TARGET), native)
	.DEFAULT_GOAL := build/native/libmymod.a

else
	.DEFAULT_GOAL := usage
endif

OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))

$(BUILD_DIR):
	mkdir -p $@

build/$(TARGET)/libmymod.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -I. -c $< -o $@

clean:
	rm -rf build

usage:
	@echo "Usage: make TARGET=[wasi|native]"
