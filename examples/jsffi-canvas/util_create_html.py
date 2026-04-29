from pathlib import Path

from fasthtml.common import (
    H1,
    Body,
    Canvas,
    Div,
    Head,
    Html,
    Input,
    Label,
    Link,
    Meta,
    NotStr,
    P,
    Script,
    Span,
    Title,
)


def slider(id, label, min, max, value, step=1, display_suffix=""):
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


def demo_page(name, lang):
    demo_names = ["particles", "image_data"]
    if name not in demo_names:
        raise ValueError(f"{name} must be in {demo_names}")
    elif name == "particles":
        sliders = [
            slider("nParticles", "Particles", 2, 80, 20, 1),
            slider("speed", "Speed", 1, 10, 3, 0.5, " px/f"),
            slider("radius", "Radius", 2, 20, 6, 1, " px"),
        ]
    else:
        sliders = [
            slider("red", "Red", 0, 255, 255),
            slider("green", "Green", 0, 255, 255),
            slider("blue", "Blue", 0, 255, 0),
        ]

    ext_src = ".spy" if lang == "SPy" else ".js"
    base_finename = "demo_" + name
    filename = base_finename + ext_src

    if lang == "JS":
        script = Script(src=filename, defer=True)
        lang_label = "JavaScript"
        hljs_lang = "javascript"
    elif lang == "SPy":
        script = Script(src=f"build/{base_finename}.mjs", type="module")
        lang_label = "SPy"
        hljs_lang = "python"
    else:
        raise NotImplementedError

    source = Path(filename).read_text(encoding="utf-8")

    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(f"{lang} — Canvas Demo"),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css",
            ),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/tailwindcss@3.4.1/base.min.css",
            ),
            # highlight.js — atom-one-dark fits the night theme perfectly
            Link(
                rel="stylesheet",
                href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css",
            ),
            Script(
                src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"
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
.gap-2 { gap: 0.5rem; }
.p-8 { padding: 2rem; }
.p-4 { padding: 1rem; }
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
.text-xs { font-size: 0.75rem; line-height: 1rem; }
.text-base { font-size: 1rem; }
.rounded-xl { border-radius: 0.75rem; }
.rounded-2xl { border-radius: 1rem; }
.overflow-hidden { overflow: hidden; }
.overflow-x-auto { overflow-x: auto; }
.shrink-0 { flex-shrink: 0; }
.items-start { align-items: flex-start; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.border { border-width: 1px; }
.border-base-300 { border-color: oklch(var(--b3) / 1); }
canvas { display: block; }
/* Override hljs background to blend with card */
.hljs { background: transparent !important; padding: 0 !important; }
pre { margin: 0; }
</style>"""
            ),
        ),
        Body(
            Div(
                # Header
                Div(
                    H1(f"{lang} Demo", cls="text-3xl font-bold text-primary"),
                    P(
                        "Placeholder for a future SPy/WASM demo.",
                        cls="text-sm text-base-content/50 pb-2",
                    ),
                    cls="flex flex-col gap-1",
                ),
                # Main content: canvas + controls side by side
                Div(
                    # Canvas
                    Div(
                        Canvas(
                            id="canvas",
                            cls="w-full h-full rounded-xl",
                            width="800",
                            height="600",
                        ),
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
                            *sliders,
                            cls="flex flex-col gap-6",
                        ),
                        cls="card bg-base-200 p-8 flex flex-col gap-6 w-full",
                    ),
                    cls="flex flex-row gap-8 items-start",
                ),
                # Source code explanation + display
                Div(
                    P(
                        f"The {lang_label} source code below is what drives the animation above. "
                        + (
                            "It is compiled to WebAssembly by the SPy compiler and runs directly in your browser — no Python runtime, no PyScript, no Pyodide."
                            if lang == "SPy"
                            else "It runs natively in your browser via a standard script tag."
                        ),
                        cls="text-sm text-base-content/60",
                    ),
                    cls="px-1",
                ),
                Div(
                    Div(
                        Div(
                            Span(
                                filename, cls="font-mono text-sm text-base-content/70"
                            ),
                            Span(
                                lang_label, cls="badge badge-primary badge-sm font-mono"
                            ),
                            cls="flex items-center justify-between",
                        ),
                        NotStr(
                            f'<div class="overflow-x-auto"><pre><code class="language-{hljs_lang}">'
                            + source.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                            + "</code></pre></div>"
                        ),
                        cls="flex flex-col gap-2 p-4",
                    ),
                    cls="card bg-base-200 border border-base-300 overflow-hidden rounded-2xl",
                ),
                cls="flex flex-col gap-6 p-8 max-w-5xl mx-auto min-h-screen",
            ),
            script,
            # Initialise highlight.js after DOM is ready
            Script(
                "document.addEventListener('DOMContentLoaded', () => hljs.highlightAll());"
            ),
            **{"data-theme": "night"},
        ),
        lang="en",
    )


def create_html(name, lang):
    if lang == "JS":
        path_output = f"demo_{name}.html"
    else:
        path_output = "index.html"

    Path(path_output).write_text(str(demo_page(name, lang)), encoding="utf-8")
    print(f"Written {path_output}")
