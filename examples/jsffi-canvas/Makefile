
ifeq ($(RELEASE),1)
RELEASE_FLAG=--release
else
RELEASE_FLAG=
endif

build: html-spy-image_data build-wasm-image_data

html-spy-image_data:
	uv run python -c 'from util_create_html import create_html as c; c("image_data", "SPy")'

html-spy-particles:
	uv run python -c 'from util_create_html import create_html as c; c("particles", "SPy")'

build-wasm-image_data:
	uv run spy build ${RELEASE_FLAG} --target emscripten demo_image_data.spy

build-wasm-particles:
	uv run spy build ${RELEASE_FLAG} --target emscripten demo_particles.spy

serve:
	uv run python -m http.server

html-js-image_data:
	uv run python -c 'from util_create_html import create_html as c; c("image_data", "JS")'

html-js-particles:
	uv run python -c 'from util_create_html import create_html as c; c("particles", "JS")'

format:
	ruff format
	ruff check --fix

clean:
	rm -rf build *.html
