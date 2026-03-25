import asyncio
import base64
import sys
import time
import tomllib
import zlib
from pathlib import Path

import ltk
from js import console, window

console.log("[Python] main.py started executing")

# ========== SPy code ==========

console.log("[Python] Installing spy package...")
print("Installing spy... ", end="")
sys.stdout.flush()
import micropip

await micropip.install("./spylang-0.1.0-py3-none-any.whl")
print("DONE")
console.log("[Python] SPy package installed successfully")

from js import URL, document

console.log("[Python] Importing spy.cli and libspy...")
import spy.cli
from spy import libspy

console.log("[Python] SPy imports complete")

libspy.LIBSPY_WASM = str(URL.new("./libspy.mjs", document.baseURI))


def spy_main(argv):
    try:
        return spy.cli.app(argv)
    except SystemExit:
        pass


# =========== GUI code ==========


class Editor(ltk.Div):
    classes = ["editor"]

    def __init__(self, value):
        ltk.Div.__init__(self)
        self.create(value)
        ltk.schedule(lambda: self.editor.refresh(value), "Refresh after load")

    def create(self, value):
        config = ltk.to_js(
            {
                "mode": {
                    "name": "python",
                    "version": 3,
                    "singleLineStringErrors": False,
                },
                "lineNumbers": True,
                "indentUnit": 4,
                "matchBrackets": True,
            }
        )
        self.editor = ltk.window.CodeMirror(self.element[0], config)
        self.editor.setSize("100%", "100%")
        self.text(value)

    def text(self, text=None):
        return (
            self.editor.setValue(text) if text is not None else self.editor.getValue()
        )


# Auto-discover example files from pyscript.toml
console.log("[Python] Loading example files from pyscript.toml...")
with open("pyscript.toml", "rb") as f:
    config = tomllib.load(f)
EXAMPLE_FILES = [
    f"examples/{source}"
    for source, dest in config.get("files", {}).items()
    if dest == "examples/"
]


def load_shared_code_from_url() -> None:
    SHARED_FILENAME = "examples/shared.spy"
    hash_str = str(window.location.hash)
    if hash_str.startswith("#code="):
        encoded = hash_str[len("#code=") :]
        try:
            compressed = base64.urlsafe_b64decode(encoded)
            code = zlib.decompress(compressed).decode("utf-8")
            Path(SHARED_FILENAME).parent.mkdir(parents=True, exist_ok=True)
            Path(SHARED_FILENAME).write_text(code)
            EXAMPLE_FILES.insert(0, SHARED_FILENAME)
            console.log("[Python] Loaded shared code from URL into 'Shared' tab")
        except Exception as e:
            console.log(f"[Python] Failed to decode shared code from URL: {e}")


load_shared_code_from_url()


console.log(f"[Python] Creating editor with initial file: {EXAMPLE_FILES[0]}")
editor = Editor(Path(EXAMPLE_FILES[0]).read_text())
console.log("[Python] Editor created")

display_filename = "test.spy"
command_leader = "$"
INPUT_TERMINAL_LEADER = f"{command_leader} spy "
INPUT_TERMINAL_ENDER = f"{display_filename}"

term_input = (
    ltk.Input(INPUT_TERMINAL_LEADER + INPUT_TERMINAL_ENDER)
    .css("width", "100%")
    .css("padding", 5)
    .attr("id", "terminal-input")
    .addClass("command-prompt")
)


@ltk.callback
def handle_term_enter(event):
    """Validate that the input field still starts with "$ spy (filename) and
    run the SPy cli with the indicated arguments
    """
    if event.key == "Enter":
        inp = event.target
        value = inp.value

        if value.startswith(INPUT_TERMINAL_LEADER):
            _, _, argv = value.partition(INPUT_TERMINAL_LEADER)
            run_spy_file_with_args(argv.split())
            _show_terminal()
        else:
            print(f"{INPUT_TERMINAL_LEADER}{value} is not a valid command")


term_input.on("keydown", handle_term_enter)

# Create tabs for example files (display only the filename, not the path)
example_tabs = ltk.Tabs(
    *[ltk.VBox().attr("name", Path(filepath).name) for filepath in EXAMPLE_FILES]
)


# Commands that support --format html --output -
HTML_CAPABLE_COMMANDS = {"parse", "redshift", "colorize"}


def _show_terminal() -> None:
    ltk.find("#terminal").show()
    ltk.find("#html-output").hide()


def _show_html_output(html_content: str) -> None:
    ltk.find("#terminal").hide()
    ltk.find("#html-output").show()
    ltk.window.jQuery("#html-frame").prop("srcdoc", html_content)


def run_spy_file_with_args(argv: list[str]):
    """Given a list of space-delimited arguments, pass them to the spy cli"""
    __terminal__.clear()
    text = editor.text()
    with open(display_filename, "w") as f:
        f.write(text)

    spy_main(argv)


HTML_OUTPUT_FILES = {
    "parse": "build/{modname}_parse.html",
    "redshift": "build/{modname}_rs.html",
    "colorize": "build/{modname}_colorize.html",
}


async def _run_html_command_async(command: str) -> str:
    """
    Run an HTML-format spy command and return the generated HTML.

    On emscripten, spy_typer.syncify() schedules an asyncio task stored in
    spy_typer.last_task. We await it, then read the HTML file the CLI wrote.
    """
    import spy.cli.spy_typer as spy_typer

    with open(display_filename, "w") as f:
        f.write(editor.text())

    modname = Path(display_filename).stem
    argv = [command, "--format", "html", "--spyast-js", "relative", display_filename]
    spy_main(argv)

    task = spy_typer.last_task
    if task is not None:
        await task

    output_path = HTML_OUTPUT_FILES.get(command, "").format(modname=modname)
    if output_path and Path(output_path).exists():
        return Path(output_path).read_text()
    console.log(f"[Python] HTML output file not found: {output_path!r}")
    return ""


async def _run_click_html(command: str) -> None:
    html_content = await _run_html_command_async(command)
    if html_content.strip():
        _show_html_output(html_content)
    else:
        _show_terminal()


def run_click(event):
    """Pass the text label of a button as args to the Spy cli"""
    element = ltk.find(event.target)
    flag_value = element.text().lower()
    base_command = flag_value.split()[0]
    backend = str(ltk.find("#backend-select").val())

    inp = ltk.window.document.getElementById("terminal-input")
    inp.value = f"{command_leader} spy {flag_value} {display_filename}"

    if backend == "HTML" and base_command in HTML_CAPABLE_COMMANDS:
        __terminal__.clear()
        asyncio.ensure_future(_run_click_html(base_command))
    else:
        argv = flag_value.split() + [display_filename]
        console.log(f"[Python] WASM backend: spy {' '.join(argv)}")
        run_spy_file_with_args(argv)
        _show_terminal()


def ButtonLabel(text):
    btn = ltk.Button(text, lambda: None)
    btn.addClass("base-button")
    btn.addClass("label-button")
    return btn


def RunSPyButton(text):
    btn = ltk.Button(text, run_click)
    btn.addClass("run-button")
    btn.addClass("base-button")
    return btn


def share_click(event):
    text = editor.text()
    compressed = zlib.compress(text.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    new_url = str(window.location.href).split("#")[0] + "#code=" + encoded
    window.navigator.clipboard.writeText(new_url)
    console.log(f"[Python] Share URL copied to clipboard")

    btn = ltk.find(event.target)
    btn.text("Copied! ✓")
    ltk.schedule(lambda: btn.text("Share"), "Reset share button", 1)


def RunShareButton():
    btn = ltk.Button("Share", share_click)
    btn.addClass("run-button")
    btn.addClass("base-button")
    return btn


@ltk.callback
def tab_activated(event, ui=None):
    # Load the selected example file into the editor
    index = example_tabs.active()
    filename = EXAMPLE_FILES[index]
    src = Path(filename).read_text()
    editor.text(src)


def main():
    console.log("[Python] main() function started - building GUI...")

    # Register tab activation callback
    example_tabs.on("tabsactivate", tab_activated)
    example_tabs.find(".ui-tabs-panel").hide()

    (
        ltk.VBox(
            example_tabs,
            ltk.HBox(
                ltk.Label(f"{display_filename}"),
                RunShareButton().css("margin-left", "auto"),
            ).css("margin", "5px"),
            editor.css("border", "1px solid gray")
            .css("height", 405)
            .attr("id", "editor"),
            ltk.VBox(
                ltk.Label("Try the SPy CLI:"),
                term_input,
                ltk.Div(
                    ButtonLabel("Sample Flags:"),
                    RunSPyButton("execute"),
                    RunSPyButton("parse"),
                    RunSPyButton("redshift"),
                    RunSPyButton("redshift --full-fqn"),
                    RunSPyButton("build --cdump"),
                    RunSPyButton("colorize"),
                    ltk.Label("Backend:")
                    .css("margin-left", "10px")
                    .css("align-self", "center"),
                    ltk.Select(["WASM", "HTML"], "WASM").attr("id", "backend-select"),
                ).css({"display": "flex", "gap": "5px", "vertical-align": "bottom"}),
            ).css(
                {
                    "align-items": "flex-start",
                }
            ),
            ltk.Div().attr("id", "terminal"),
        )
        .css("width", 1200)
        .css("font-size", 14)
        .attr("name", "Editor")
        .appendTo(ltk.window.document.body)
    )

    ltk.find("#terminal").append(ltk.find("py-terminal"))

    ltk.window.jQuery('[name="Editor"]').append(
        '<div id="html-output" style="display:none">'
        '<iframe id="html-frame" style="width:100%;height:600px;border:none"></iframe>'
        "</div>"
    )

    console.log("[Python] GUI construction complete - playground ready!")


console.log("[Python] Calling main()...")
main()
