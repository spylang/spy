# type: ignore

import base64
import sys
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
                "indentWithTabs": False,
                "matchBrackets": True,
                "extraKeys": {"Tab": "indentMore", "Shift-Tab": "indentLess"},
            }
        )
        self.editor = ltk.window.CodeMirror(self.element[0], config)
        self.editor.setSize("100%", "100%")
        self.text(value)

    def text(self, text=None):
        return (
            self.editor.setValue(text) if text is not None else self.editor.getValue()
        )


# Auto-discover example files from pyscript.toml, grouped by category
console.log("[Python] Loading example files from pyscript.toml...")
with open("pyscript.toml", "rb") as f:
    config = tomllib.load(f)

# CATEGORIES: dict mapping category dir name -> list of file paths
# e.g. {"1_high_level": ["examples/1_high_level/hello.spy", ...], ...}
CATEGORIES: dict[str, list[str]] = {}
for source, dest in config.get("files", {}).items():
    if dest.startswith("examples/"):
        category = Path(source).parent.name  # e.g. "1_high_level"
        CATEGORIES.setdefault(category, []).append(source)

# Pretty labels for the outer tabs
CATEGORY_LABELS = {
    "1_high_level": "1 \u00b7 High Level",
    "2_metaprogramming": "2 \u00b7 Metaprogramming",
    "3_low_level": "3 \u00b7 Low Level",
    "4_advanced": "4 \u00b7 Advanced",
}


def category_label(cat: str) -> str:
    return CATEGORY_LABELS.get(cat, cat)


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
            shared_entry = {"shared": [SHARED_FILENAME]}
            shared_entry.update(CATEGORIES)
            CATEGORIES.clear()
            CATEGORIES.update(shared_entry)
            console.log("[Python] Loaded shared code from URL into 'Shared' tab")
        except Exception as e:
            console.log(f"[Python] Failed to decode shared code from URL: {e}")


load_shared_code_from_url()

# Currently selected file path
current_file: str = next(iter(CATEGORIES.values()))[0]

console.log(f"[Python] Creating editor with initial file: {current_file}")
editor = Editor(Path(current_file).read_text())
console.log("[Python] Editor created")

command_leader = "$"
INPUT_TERMINAL_LEADER = f"{command_leader} spy "


def display_filename() -> str:
    return Path(current_file).name


term_input = (
    ltk.Input(INPUT_TERMINAL_LEADER + display_filename())
    .css("flex", "1")
    .css("padding", 5)
    .attr("id", "terminal-input")
    .attr("title", "Edit arguments then press Enter or click Run")
    .addClass("command-prompt")
)


def run_input_click(event):
    """Run what is written in the terminal input"""
    run_input_if_validated()


term_input_run_btn = ltk.Button("Run ▶", run_input_click)
term_input_run_btn.addClass("run-button").addClass("base-button")


@ltk.callback
def handle_term_enter(event):
    """Run the command on Enter key"""
    if event.key == "Enter":
        run_input_if_validated()


def run_input_if_validated():
    """Validate that the input field still starts with "$ spy (filename) and
    run the SPy cli with the indicated arguments
    """
    value = term_input.val()
    if value.startswith(INPUT_TERMINAL_LEADER):
        _, _, argv = value.partition(INPUT_TERMINAL_LEADER)
        run_spy_file_with_args(argv.split())
    else:
        print(f"{value} is not a valid command")


term_input.on("keydown", handle_term_enter)


def run_spy_file_with_args(argv: list[str]):
    """Given a list of space-delimited arguments, pass them to the spy cli"""
    __terminal__.clear()
    text = editor.text()
    with open(display_filename(), "w") as f:
        f.write(text)

    # This try/except avoids SystemExit being turned into an error.
    # No such issue with Firefox but this is useful for others browsers.
    try:
        spy.cli.app(argv)
    except SystemExit:
        pass


def run_click(event):
    """Pass the text label of a button as args to the Spy cli"""
    element = ltk.find(event.target)
    flag_value = element.text().lower()

    new_input_value = f"{command_leader} spy {flag_value} {display_filename()}"
    console.log("Setting input value to " + new_input_value)
    term_input.val(new_input_value)

    run_spy_file_with_args(flag_value.split() + [display_filename()])


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


filename_label = ltk.Label(display_filename())


def load_file(filepath: str) -> None:
    """Load a file into the editor and update the UI accordingly."""
    global current_file
    current_file = filepath
    console.log(f"load_file: {filepath = }, {current_file = }")
    editor.text(Path(filepath).read_text(encoding="utf-8"))
    term_input.val(INPUT_TERMINAL_LEADER + display_filename())
    filename_label.text(display_filename())


def make_file_explorer() -> ltk.Div:
    """Build a file-explorer sidebar: collapsible category sections with file items."""
    explorer = ltk.Div().addClass("file-explorer")

    for cat, files in CATEGORIES.items():
        label = category_label(cat)

        # Category header (clickable to collapse/expand)
        header = ltk.Div(ltk.Span("▾ ").addClass("caret"), ltk.Span(label))
        header.addClass("fe-category")

        # File list container
        file_list = ltk.Div().addClass("fe-file-list")

        for filepath in files:
            fname = Path(filepath).name
            item = ltk.Div(fname).addClass("fe-file-item")
            if filepath == current_file:
                item.addClass("fe-file-active")

            @ltk.callback
            def on_file_click(event, _fp=filepath, _item=item):
                # Deactivate all items, activate clicked one
                ltk.find(".fe-file-item").removeClass("fe-file-active")
                _item.addClass("fe-file-active")
                load_file(_fp)

            item.on("click", on_file_click)
            file_list.append(item)

        # Toggle collapse on header click
        @ltk.callback
        def on_header_click(event, _fl=file_list, _hdr=header):
            caret = _hdr.find(".caret")
            if _fl.is_(":visible"):
                _fl.hide()
                caret.text("▸ ")
            else:
                _fl.show()
                caret.text("▾ ")

        header.on("click", on_header_click)
        explorer.append(header)
        explorer.append(file_list)

    return explorer


def main():
    console.log("[Python] main() function started - building GUI...")

    file_explorer = make_file_explorer()

    editor_panel = ltk.VBox(
        ltk.HBox(
            filename_label,
            RunShareButton().css("margin-left", "auto"),
        ).css("margin", "5px"),
        editor.css("border", "1px solid gray").attr("id", "editor"),
        ltk.VBox(
            ltk.Label("Try the SPy CLI:"),
            ltk.HBox(
                term_input,
                term_input_run_btn,
            ).css({"width": "100%", "display": "flex", "gap": "5px"}),
            ltk.Div(
                ButtonLabel("Sample Flags:"),
                RunSPyButton("execute"),
                RunSPyButton("parse"),
                RunSPyButton("colorize"),
                RunSPyButton("redshift"),
                RunSPyButton("redshift --linearize"),
                RunSPyButton("redshift --full-fqn"),
                RunSPyButton("redshift --execute"),
                RunSPyButton("build --cdump"),
            ).css({"display": "flex", "gap": "5px", "vertical-align": "bottom"}),
        ).css(
            {
                "align-items": "flex-start",
            }
        ),
        ltk.Div().attr("id", "terminal"),
    ).addClass("editor-panel")

    (
        ltk.HBox(
            file_explorer,
            editor_panel,
        )
        .css(
            {
                "width": "95%",
                "max-width": "1600px",
                "margin": "20px auto",
                "align-items": "flex-start",
            }
        )
        .css("font-size", 14)
        .attr("name", "Editor")
        .appendTo(ltk.window.document.body)
    )

    ltk.find("#terminal").append(ltk.find("py-terminal"))
    console.log("[Python] GUI construction complete - playground ready!")


console.log("[Python] Calling main()...")
main()
