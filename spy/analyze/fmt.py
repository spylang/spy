import os
import subprocess
import tempfile

from spy.magic_py_parse import (
    construct_SPy_specific_grammar,
    preprocess,
    reinsert_spy_specific_grammar,
)
from spy.parser import Parser
from spy.vendored import untokenize
from spy.vm.vm import SPyVM


def format_python_source_with_ruff(source: str) -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    fd, tmp_path = tempfile.mkstemp(dir=repo_root, suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        try:
            subprocess.run(
                ["ruff", "format", tmp_path],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ruff executable not found") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise RuntimeError(f"ruff format failed: {message}") from exc
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


class SPyFormatter:
    def __init__(self, vm: "SPyVM") -> None:
        self.vm = vm

    def format(self, modname: str) -> None:
        spyfile = self.vm.find_file_on_path(modname)
        if spyfile is None:
            return
        if not spyfile.exists() or not spyfile.isfile():
            return
        parser = Parser.from_filename(str(spyfile))
        parser.parse()

        spy_src = parser.src
        py_src, _ = preprocess(spy_src, parser.filename)

        spy_grammar_tracker = construct_SPy_specific_grammar(spy_src)
        formatted_py_src = format_python_source_with_ruff(py_src)
        tokens = reinsert_spy_specific_grammar(formatted_py_src, spy_grammar_tracker)
        formatted_spy_src = untokenize.untokenize(tokens)

        with open(spyfile, "w", encoding="utf-8") as f:
            f.write(formatted_spy_src)
