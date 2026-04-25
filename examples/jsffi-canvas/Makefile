
build: html_spy build-wasm

html_spy:
	uv run python make_html_spy.py

build-wasm:
	uv run spy build --target emscripten demo.spy

build-wasm-release:
	uv run spy build --release --target emscripten demo.spy

serve:
	uv run python -m http.server

html_js:
	uv run python make_html_js.py

format:
	ruff format
	ruff check --fix
