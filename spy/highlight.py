import re
import sys
from pathlib import Path
from typing import Literal, Optional

from spy.textbuilder import Color


def highlight_src(lang: Literal["C", "spy"], code: str) -> str:
    """
    Simple regexp-based syntax highlighter for C and SPy code.
    Returns the code with ANSI color codes applied.
    """
    if lang == "spy":
        return _highlight_spy(code)
    else:
        return _highlight_c(code)


def _highlight_spy(code: str) -> str:
    """
    Highlight SPy code (Python-like syntax with FQN support).
    """
    result = []

    # Token patterns (order matters for precedence)
    # Color names must match ColorFormatter attributes
    patterns = [
        # Comments
        (r"#[^\n]*", "darkgray"),
        # Strings (triple-quoted first, then single/double)
        (r'"""(?:[^\\"]|\\.|"(?!""))*"""', "green"),
        (r"'''(?:[^\\']|\\.|'(?!''))*'''", "green"),
        (r'"(?:[^\\"\n]|\\.)*"', "green"),
        (r"'(?:[^\\'\n]|\\.)*'", "green"),
        # Fully qualified names in backticks
        (r"`[^`]+`", "fuchsia"),
        # Keywords
        (
            r"\b(?:def|class|if|elif|else|for|while|return|import|from|as|"
            r"pass|break|continue|try|except|finally|raise|with|assert|"
            r"lambda|yield|global|nonlocal|True|False|None|and|or|not|in|is)\b",
            "blue",
        ),
        # Built-in types
        (
            r"\b(?:int|str|float|bool|list|dict|tuple|set|i32|i64|f64|dynamic|void)\b",
            "fuchsia",
        ),
        # Numbers
        (r"\b\d+\.?\d*(?:[eE][+-]?\d+)?\b", "yellow"),
        # Function/method calls (identifier followed by parenthesis)
        (r"\b([a-zA-Z_]\w*)(?=\s*\()", "default"),
    ]

    lines = code.split("\n")
    for line in lines:
        result.append(_highlight_line(line, patterns))
        result.append("\n")

    # Remove the last newline if original didn't have it
    if not code.endswith("\n"):
        result.pop()

    return "".join(result)


def _highlight_c(code: str) -> str:
    """
    Highlight C code.
    """
    result = []

    # Token patterns (order matters for precedence)
    # Color names must match ColorFormatter attributes
    patterns = [
        # Comments (single-line and multi-line)
        (r"//[^\n]*", "darkgray"),
        (r"/\*(?:[^*]|\*(?!/))*\*/", "darkgray"),
        # Strings
        (r'"(?:[^\\"\n]|\\.)*"', "green"),
        (r"'(?:[^\\'\n]|\\.)*'", "green"),
        # Preprocessor directives
        (
            r"^\s*#\s*(?:include|define|ifdef|ifndef|endif|if|else|elif|pragma|undef)\b[^\n]*",
            "turquoise",
        ),
        # Keywords
        (
            r"\b(?:auto|break|case|char|const|continue|default|do|double|else|enum|extern|"
            r"float|for|goto|if|inline|int|long|register|restrict|return|short|signed|"
            r"sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|"
            r"_Bool|_Complex|_Imaginary)\b",
            "blue",
        ),
        # Built-in types and common type names
        (
            r"\b(?:int8_t|int16_t|int32_t|int64_t|uint8_t|uint16_t|uint32_t|uint64_t|"
            r"size_t|ssize_t|ptrdiff_t|intptr_t|uintptr_t|FILE|bool|true|false|NULL)\b",
            "fuchsia",
        ),
        # Numbers (hex, octal, decimal, float)
        (r"\b0[xX][0-9a-fA-F]+[uUlL]*\b", "yellow"),
        (r"\b0[0-7]+[uUlL]*\b", "yellow"),
        (r"\b\d+\.?\d*(?:[eE][+-]?\d+)?[fFlL]*\b", "yellow"),
        # Function calls
        (r"\b([a-zA-Z_]\w*)(?=\s*\()", "default"),
    ]

    lines = code.split("\n")
    for line in lines:
        result.append(_highlight_line(line, patterns))
        result.append("\n")

    # Remove the last newline if original didn't have it
    if not code.endswith("\n"):
        result.pop()

    return "".join(result)


def _highlight_line(line: str, patterns: list[tuple[str, str]]) -> str:
    """
    Apply syntax highlighting to a single line.
    patterns: list of (regex_pattern, color_name) tuples
    """
    if not line:
        return line

    # Find all matches with their positions
    matches = []
    for pattern, color in patterns:
        for match in re.finditer(pattern, line, re.MULTILINE):
            matches.append((match.start(), match.end(), color, match.group()))

    # Sort by start position
    matches.sort(key=lambda x: x[0])

    # Build result, resolving overlaps by taking first match
    result = []
    pos = 0
    i = 0

    while i < len(matches):
        start, end, color, text = matches[i]

        # Skip if this match is within a previous match
        if start < pos:
            i += 1
            continue

        # Add unmatched text before this match
        if start > pos:
            result.append(line[pos:start])

        # Add colored match
        result.append(Color.set(color, text))
        pos = end
        i += 1

    # Add remaining unmatched text
    if pos < len(line):
        result.append(line[pos:])

    return "".join(result)


def detect_language(filename: str) -> Literal["C", "spy"]:
    """
    Auto-detect language from file extension.
    """
    path = Path(filename)
    ext = path.suffix.lower()
    if ext in [".c", ".h"]:
        return "C"
    else:
        return "spy"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Simple syntax highlighter for C and SPy code"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Source file to highlight (reads from stdin if not provided)",
    )
    parser.add_argument(
        "-l",
        "--lang",
        choices=["C", "spy"],
        help="Language to use for highlighting (auto-detected from file extension if not provided)",
    )

    args = parser.parse_args()

    # Determine language
    if args.lang:
        lang = args.lang
    elif args.file:
        lang = detect_language(args.file)
    else:
        # Default to spy for stdin
        lang = "spy"

    # Read input
    if args.file:
        with open(args.file) as f:
            code = f.read()
    else:
        code = sys.stdin.read()

    # Highlight and print
    print(highlight_src(lang, code), end="")
