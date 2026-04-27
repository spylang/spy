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
