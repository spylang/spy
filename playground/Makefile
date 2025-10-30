.PHONY: local clean

# Paths relative to playground directory
ROOT_DIR := ..
LIBSPY_DIR := $(ROOT_DIR)/spy/libspy
BUILD_DIR := $(LIBSPY_DIR)/build/emscripten/release
DIST_DIR := $(ROOT_DIR)/dist

# Detect uv and use it if available, otherwise use python directly
UV := $(shell command -v uv 2>/dev/null)
ifdef UV
    PYTHON := uv run python
else
    PYTHON := python
endif

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
