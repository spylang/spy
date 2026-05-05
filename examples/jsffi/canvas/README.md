# SPy canvas demos — no PyScript, no JavaScript

This directory contains browser demos showing how SPy/WASM can drive a webpage
interactively — including 60fps canvas animations — without PyScript, Pyodide, or any
hand-written JavaScript logic. The only JS present is the small Emscripten bootstrap
generated automatically by the SPy compiler.

The HTML pages are generated with FastHTML and Python (Tailwind/DaisyUI for styling). The
dynamic part — simulation, rendering, event handling — is entirely written in SPy and
compiled to WebAssembly with Emscripten.

Two demos are available:

- **image_data** — a colour animation driven by RGB sliders, rendered via `putImageData`
  into a canvas pixel buffer.
- **particles** — a 60fps bouncing particle simulation using the canvas 2D API (`arc`,
  `fillRect`, `createRadialGradient`), with controls for particle count, speed, and
  radius.

In release mode (`RELEASE=1`) the compiled binaries are remarkably small: the `.wasm`
file is around **27 KB** and the Emscripten glue `.mjs` around **64 KB**, for a total of
roughly **91 KB** — smaller than a typical webpage image, and orders of magnitude smaller
than a PyScript/Pyodide deployment (~10 MB).

## Requirements

- `uv`
- `emcc` (Emscripten)

## Building and serving

To build and serve both SPy demos:

```sh
make build
make serve
```

To build in release mode:

```sh
make build RELEASE=1
```

## JavaScript equivalents

Reference JS implementations are provided for comparison. To view them:

```sh
make html-js-image_data
firefox demo_image_data.html

make html-js-particles
firefox demo_particles.html
```

## Building individual demos for deployment

To produce a self-contained deployable folder for each demo:

**particles:**

```sh
make clean
make html-spy-particles
make build-wasm-particles RELEASE=1
mkdir -p build/output-spy-particles/build
mv index.html build/output-spy-particles
mv build/demo_particles.* build/output-spy-particles/build
```

**image_data:**

```sh
make clean
make html-spy-image_data
make build-wasm-image_data RELEASE=1
mkdir -p build/output-spy-image_data/build
mv index.html build/output-spy-image_data
mv build/demo_image_data.* build/output-spy-image_data/build
```

Each output folder contains a static `index.html` and a `build/` subdirectory with the
`.mjs` and `.wasm` files — ready to deploy on GitHub Pages or any static host.
