const WIDTH = 800;
const HEIGHT = 600;
const SIZE = WIDTH * HEIGHT * 4;

const params = { red: 0, green: 0, blue: 0 };

let counter = 0;
let inc = 5;
const buf = new Uint8Array(SIZE);

function simulateStep() {
    if (inc > 0 && counter + inc > 255) inc *= -1;
    else if (inc < 0 && counter + inc < 0) inc *= -1;
    counter += inc;

    for (let idx = 0; idx < WIDTH * HEIGHT; idx++) {
        buf[idx * 4 + 0] = (params.red   * counter) / 255 | 0;
        buf[idx * 4 + 1] = (params.green * counter) / 255 | 0;
        buf[idx * 4 + 2] = (params.blue  * counter) / 255 | 0;
        buf[idx * 4 + 3] = counter;
    }
}

function syncSlider(id) {
    const value = parseInt(document.getElementById(id).value);
    document.getElementById(id + "Val").textContent = value;
    params[id] = value;
}

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

function frame() {
    simulateStep();
    const imageData = new ImageData(new Uint8ClampedArray(buf.buffer), WIDTH, HEIGHT);
    ctx.putImageData(imageData, 0, 0);
    requestAnimationFrame(frame);
}

for (const id of ["red", "green", "blue"]) {
    const elem = document.getElementById(id);
    params[id] = parseInt(elem.value);
    elem.addEventListener("input", () => syncSlider(id));
}

buf.fill(255);
requestAnimationFrame(frame);
