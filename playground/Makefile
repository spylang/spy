.PHONY: local clean

# Paths relative to playground directory
ROOT_DIR := ..
LIBSPY_DIR := $(ROOT_DIR)/spy/libspy
BUILD_DIR := $(LIBSPY_DIR)/build/emscripten/release
DIST_DIR := $(ROOT_DIR)/dist

# Use $PYTHON from environment if set, otherwise default to just 'python'
# NOTE: Use only a single executable name if you set $PYTHON
# if you set $PYTHON to an executable with arguments, i.e. 'uv run python',
# emcc will fail to run as it tries to call exec() with the whole string.
# We don't run emcc here, but other parts of the project do. If you do want
# to use 'uv run python', you could put the following two lines into a separate
# runner:
# #!/bin/sh
# exec uv run python "$@"
PYTHON ?= python

# Get version from pyproject.toml
VERSION := $(shell $(PYTHON) -c "import tomllib; print(tomllib.load(open('$(ROOT_DIR)/pyproject.toml', 'rb'))['project']['version'])")
WHEEL_NAME := spylang-$(VERSION)-py3-none-any.whl

# Build playground for local development
# This mirrors the steps from .github/workflows/playground.yml
local:
	@echo "Building libspy for emscripten..."
	$(MAKE) -C $(LIBSPY_DIR) TARGET=emscripten

	@echo "Building Python wheel..."
	$(PYTHON) -m build --wheel --outdir $(DIST_DIR) $(ROOT_DIR)

	@echo "Updating main.py with wheel filename..."
	sed -i.bak "s|spylang-.*-py3-none-any\.whl|$(WHEEL_NAME)|g" main.py && rm -f main.py.bak

	@echo "Copying built files to playground..."
	cp $(BUILD_DIR)/libspy.mjs .
	cp $(BUILD_DIR)/libspy.wasm .
	cp $(DIST_DIR)/spylang-*.whl .

	@echo "✓ Playground built successfully!"
	@echo "Run 'python -m http.server' in this directory to test locally"

clean:
	rm -f libspy.mjs libspy.wasm spylang-*.whl
