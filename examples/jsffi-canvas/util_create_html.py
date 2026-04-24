from fasthtml.common import H1, Body, Canvas, Div, Head, Html, Input
from fasthtml.common import Label, Link, Meta, NotStr, P, Script, Span, Title


def slider(id, label, min, max, value, step, display_suffix=""):
    return Div(
        Div(
            Label(label, cls="label-text text-base-content/70 text-sm font-medium"),
            Span(
                str(value) + display_suffix,
                id=f"{id}Val",
                cls="label-text-alt text-primary font-mono text-sm",
            ),
            cls="label",
        ),
        Input(
            type="range",
            id=id,
            name=id,
            min=str(min),
            max=str(max),
            value=str(value),
            step=str(step),
            cls="range range-primary range-sm",
        ),
        cls="form-control gap-1",
    )


def demo_page(lang):
    if lang == "JS":
        script = Script(src="demo.js", defer=True)
    elif lang == "spy":
        script = Script(src="build/demo.mjs", type="module")
    else:
        raise NotImplementedError

    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("SPy — Particle Demo"),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css",
            ),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/tailwindcss@3.4.1/base.min.css",
            ),
            # Inline the minimal Tailwind utilities DaisyUI depends on
            NotStr(
                """<style>
*, ::before, ::after { box-sizing: border-box; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-row { flex-direction: row; }
.gap-6 { gap: 1.5rem; }
.gap-8 { gap: 2rem; }
.p-8 { padding: 2rem; }
.pb-2 { padding-bottom: 0.5rem; }
.min-h-screen { min-height: 100vh; }
.w-full { width: 100%; }
.h-full { height: 100%; }
.max-w-5xl { max-width: 64rem; }
.mx-auto { margin-left: auto; margin-right: auto; }
.font-bold { font-weight: 700; }
.font-mono { font-family: ui-monospace, monospace; }
.text-3xl { font-size: 1.875rem; line-height: 2.25rem; }
.text-sm { font-size: 0.875rem; line-height: 1.25rem; }
.text-base { font-size: 1rem; }
.rounded-xl { border-radius: 0.75rem; }
.rounded-2xl { border-radius: 1rem; }
.overflow-hidden { overflow: hidden; }
.shrink-0 { flex-shrink: 0; }
.items-start { align-items: flex-start; }
.border { border-width: 1px; }
.border-base-300 { border-color: oklch(var(--b3) / 1); }
canvas { display: block; }
</style>"""
            ),
        ),
        Body(
            Div(
                # Header
                Div(
                    H1("SPy Particle Demo", cls="text-3xl font-bold text-primary"),
                    P(
                        "Bouncing particles — placeholder for a future SPy/WASM simulation.",
                        cls="text-sm text-base-content/50 pb-2",
                    ),
                    cls="flex flex-col gap-1",
                ),
                # Main content: canvas + controls side by side
                Div(
                    # Canvas
                    Div(
                        Canvas(id="demoCanvas", cls="w-full h-full rounded-xl"),
                        cls="rounded-2xl overflow-hidden border border-base-300 shrink-0",
                        style="width:600px; height:400px; background:#0f172a;",
                    ),
                    # Controls panel
                    Div(
                        Div(
                            P(
                                "Parameters",
                                cls="text-base font-bold text-base-content/80",
                            ),
                            slider("nParticles", "Particles", 2, 80, 20, 1),
                            slider("speed", "Speed", 1, 10, 3, 0.5, " px/f"),
                            slider("radius", "Radius", 2, 20, 6, 1, " px"),
                            cls="flex flex-col gap-6",
                        ),
                        cls="card bg-base-200 p-8 flex flex-col gap-6 w-full",
                    ),
                    cls="flex flex-row gap-8 items-start",
                ),
                cls="flex flex-col gap-6 p-8 max-w-5xl mx-auto min-h-screen",
            ),
            script,
            **{"data-theme": "night"},
        ),
        lang="en",
    )
