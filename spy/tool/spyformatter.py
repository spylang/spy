import os
import subprocess
import tempfile

from spy.analyze.importing import ImportAnalyzer
from spy.magic_py_parse import (
    preprocess,
    reintroduce_spy_grammar,
)
from spy.parser import Parser


def format_python_source_with_ruff(source: str) -> tuple[str, str]:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    stdout_message = ""
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        try:
            result = subprocess.run(
                ["ruff", "format", tmp_path],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
            stdout_message = result.stdout or ""
        except FileNotFoundError as exc:
            raise RuntimeError("ruff executable not found") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise RuntimeError(f"ruff format failed: {message}") from exc
        with open(tmp_path, "r", encoding="utf-8") as f:
            return (f.read(), stdout_message)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


class SPyFormatter:
    def __init__(self, analyzer: "ImportAnalyzer") -> None:
        self.analyzer = analyzer

    def format(self, modname: str) -> None:
        spyfile = self.analyzer.find_file_on_path(modname)
        if spyfile is None:
            return
        if not spyfile.exists() or not spyfile.isfile():
            return
        parser = Parser.from_filename(str(spyfile))
        parser.parse()

        spy_src = parser.src
        py_src = preprocess(spy_src, parser.filename)

        formatted_py_src, stdout_message = format_python_source_with_ruff(py_src)
        formatted_spy_src = reintroduce_spy_grammar(formatted_py_src)

        with open(str(spyfile), "w", encoding="utf-8") as f:
            f.write(formatted_spy_src)

        print(stdout_message)
