import sys
import time
import tomllib
from pathlib import Path

import ltk
from js import console

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
        spy.cli.app(argv)
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
        else:
            print(f"{INPUT_TERMINAL_LEADER}{value} is not a valid command")


term_input.on("keydown", handle_term_enter)

# Create tabs for example files (display only the filename, not the path)
example_tabs = ltk.Tabs(
    *[ltk.VBox().attr("name", Path(filepath).name) for filepath in EXAMPLE_FILES]
)


def run_spy_file_with_args(argv: list[str]):
    """Given a list of space-delimited arguments, pass them to the spy cli"""
    __terminal__.clear()
    text = editor.text()
    with open(display_filename, "w") as f:
        f.write(text)

    spy_main(argv)


def run_click(event):
    """Pass the text label of a button as args to the Spy cli"""
    element = ltk.find(event.target)
    flag_value = element.text().lower()
    run_spy_file_with_args(flag_value.split() + [display_filename])

    inp = ltk.window.document.getElementById("terminal-input")
    console.log(
        f"Setting input value to {command_leader} spy {flag_value} {display_filename} "
    )
    inp.value = f"{command_leader} spy {flag_value} {display_filename}"


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

    (
        ltk.VBox(
            example_tabs,
            ltk.Label(f"{display_filename}"),
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
    console.log("[Python] GUI construction complete - playground ready!")


console.log("[Python] Calling main()...")
main()
