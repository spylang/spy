import sys
import time
from pathlib import Path

import ltk

# ========== SPy code ==========

print("Installing spy... ", end="")
sys.stdout.flush()
import micropip

await micropip.install("./spylang-0.1.0-py3-none-any.whl")
print("DONE")

import spy.cli
from spy import libspy

libspy.LIBSPY_WASM = "https://antocuni.pyscriptapps.com/young-disk/latest/libspy.mjs"


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


editor = Editor(Path("hello.spy").read_text())


def clear_screen():
    print("\033[2J\033[H")


def load_click(event):
    element = ltk.find(event.target)
    filename = element.text()
    src = Path(filename).read_text()
    editor.text(src)


def run_click(event):
    clear_screen()
    text = editor.text()
    with open("test.spy", "w") as f:
        f.write(text)

    element = ltk.find(event.target)
    t = element.text().lower()
    extra_argv = t.split()
    argv = ["test.spy"] + extra_argv
    # hack hack hack: for --cwrite to work, we always pass "-t native".
    # It is find to always add it as it is ignored by other passes
    argv += ["-t", "native"]
    spy_main(argv)


def LoadButton(text):
    return ltk.Button(text, load_click)


def RunSPyButton(text):
    return ltk.Button(text, run_click)


def main():
    (
        ltk.VBox(
            ltk.Div(
                LoadButton("hello.spy"),
                LoadButton("bluefunc.spy"),
                LoadButton("point.spy"),
                LoadButton("smallpoint.spy"),
                LoadButton("array.spy"),
            ),
            editor.css("border", "1px solid gray")
            .css("height", 405)
            .attr("id", "editor"),
            ltk.Div(
                ltk.Span("$ spy"),
                RunSPyButton("--execute"),
                RunSPyButton("--parse"),
                RunSPyButton("--redshift"),
                RunSPyButton("--redshift --no-pretty"),
                RunSPyButton("--cwrite"),
            ).css(
                {
                    "display": "flex",
                    "gap": "5px",
                }
            ),
            ltk.Div().attr("id", "terminal"),
        )
        .css("width", 900)
        .css("font-size", 14)
        .attr("name", "Editor")
        .appendTo(ltk.window.document.body)
    )
    ltk.find("#terminal").append(ltk.find("py-terminal"))


main()
