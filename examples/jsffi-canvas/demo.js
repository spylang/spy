const canvas = document.getElementById('demoCanvas');
const ctx = canvas.getContext('2d');

// Size canvas to its CSS dimensions
const rect = canvas.getBoundingClientRect();
canvas.width = rect.width;
canvas.height = rect.height;

// --- Slider helpers ---
function getInt(id)   { return parseInt(document.getElementById(id).value); }
function getFloat(id) { return parseFloat(document.getElementById(id).value); }

function syncLabel(id, displayId, suffix = '') {
    const el = document.getElementById(id);
    const lbl = document.getElementById(displayId);
    lbl.textContent = el.value + suffix;
    el.addEventListener('input', () => { lbl.textContent = el.value + suffix; });
}

syncLabel('nParticles', 'nParticlesVal');
syncLabel('speed',      'speedVal',  ' px/f');
syncLabel('radius',     'radiusVal', ' px');

// --- Simulation ---
let particles = [];

function initParticles() {
    const n = getInt('nParticles');
    const speed = getFloat('speed');
    const r = getInt('radius');
    particles = Array.from({ length: n }, () => {
        const angle = Math.random() * 2 * Math.PI;
        const s = (0.5 + Math.random() * 0.5) * speed;
        return {
            x: r + Math.random() * (canvas.width  - 2 * r),
            y: r + Math.random() * (canvas.height - 2 * r),
            vx: Math.cos(angle) * s,
            vy: Math.sin(angle) * s,
            hue: Math.random() * 360,
        };
    });
}

function drawParticle(p, r) {
    p.hue = (p.hue + 0.4) % 360;

    const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 2.5);
    grd.addColorStop(0, `hsla(${p.hue}, 100%, 70%, 0.6)`);
    grd.addColorStop(1, `hsla(${p.hue}, 100%, 50%, 0)`);
    ctx.beginPath();
    ctx.arc(p.x, p.y, r * 2.5, 0, Math.PI * 2);
    ctx.fillStyle = grd;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fillStyle = `hsl(${p.hue}, 100%, 75%)`;
    ctx.fill();
}

function step() {
    const speed = getFloat('speed');
    const r = getInt('radius');

    ctx.fillStyle = 'rgba(15, 23, 42, 0.25)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const p of particles) {
        // Normalise to current speed
        const v = Math.hypot(p.vx, p.vy);
        if (v > 0) { p.vx = p.vx / v * speed; p.vy = p.vy / v * speed; }

        p.x += p.vx;
        p.y += p.vy;

        if (p.x - r < 0)             { p.x = r;                p.vx *= -1; }
        if (p.x + r > canvas.width)  { p.x = canvas.width - r; p.vx *= -1; }
        if (p.y - r < 0)             { p.y = r;                p.vy *= -1; }
        if (p.y + r > canvas.height) { p.y = canvas.height - r; p.vy *= -1; }

        drawParticle(p, r);
    }

    requestAnimationFrame(step);
}

function restart() {
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    initParticles();
}

document.getElementById('nParticles').addEventListener('change', restart);
document.getElementById('radius').addEventListener('change', restart);

restart();
step();