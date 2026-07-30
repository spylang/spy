import os
import re
import subprocess
import tempfile
from pathlib import Path

import spy
from spy.errors import SPyError
from spy.magic_py_parse import preprocess, undo_preprocess


class SPyFormatter:
    def __init__(self) -> None:
        pass

    def format_python_source_with_ruff(self, source: str) -> tuple[str, str]:
        repo_root = spy.ROOT
        config_path = os.path.join(repo_root, "pyproject.toml")
        fd, tmp_path = tempfile.mkstemp(suffix=".py")
        stdout_message = ""
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(source)
            try:
                cmd = ["ruff", "format", tmp_path]
                if os.path.exists(config_path):
                    cmd.extend(["--config", config_path])
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
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

    def format(self, filename: Path) -> None:
        try:
            spy_src = filename.read_text()
            py_src = preprocess(spy_src)

            formatted_py_src, stdout_message = self.format_python_source_with_ruff(
                py_src
            )
            formatted_spy_src = undo_preprocess(formatted_py_src)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(formatted_spy_src)
            print(stdout_message)

        except Exception as exc:
            message = f"Failed to format {filename.name}: {exc}"
            raise SPyError("W_Exception", message) from exc
