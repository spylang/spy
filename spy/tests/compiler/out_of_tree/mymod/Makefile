SRCS = mymod.c

BUILD_DIR := build/$(TARGET)

ifeq ($(TARGET),)
	.DEFAULT_GOAL := usage

else ifeq ($(TARGET), wasi)
	CC    := $(shell python -m spy.libspy.flags --cc  --target=wasi)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=wasi)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=wasi) -DSPY_DEBUG -O0 -g
	.DEFAULT_GOAL := build/wasi/libmymod.a

else ifeq ($(TARGET), native)
	CC    := $(shell python -m spy.libspy.flags --cc  --target=native)
	AR    := $(shell python -m spy.libspy.flags --ar  --target=native)
	CFLAGS := $(shell python -m spy.libspy.flags --cflags --include --target=native) -DSPY_DEBUG -O0 -g
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
