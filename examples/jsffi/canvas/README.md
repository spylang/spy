# Demo website without Pyscript and JS

Requirements: uv, emcc

To build and serve the demo using SPy:

```sh
make build
make serve
```

To build in release mode, use `make build RELEASE=1`

For the JS equivalent:

```sh
make html-js-image_data
firefox demo_image_data.html

make html-js-particles
firefox demo_particles.html
```

For example, to fully build the SPy particles example:

```sh
make clean
make html-spy-particles
make build-wasm-particles RELEASE=1
mkdir -p build/output-spy-particles/build
mv index.html build/output-spy-particles
mv build/demo_particles.* build/output-spy-particles/build
```

To fully build the SPy image_data example:

```sh
make clean
make build RELEASE=1
mkdir -p build/output-spy-image_data/build
mv index.html build/output-spy-image_data
mv build/demo_image_data.* build/output-spy-image_data/build
```
