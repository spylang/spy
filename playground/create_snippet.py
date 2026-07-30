#!/usr/bin/env python3
"""
Create a shareable playground URL from a .spy file.

Usage:
    python create_snippet.py myfile.spy
    python create_snippet.py myfile.spy --url https://spylang.github.io/spy
"""

import argparse
import base64
import zlib
from pathlib import Path


def create_snippet_url(spy_file: Path, base_url: str) -> str:
    code = spy_file.read_text(encoding="utf-8")
    compressed = zlib.compress(code.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return base_url.rstrip("/") + "/#code=" + encoded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a shareable SPy playground URL from a .spy file."
    )
    parser.add_argument("file", type=Path, help="Path to the .spy file")
    parser.add_argument(
        "--url",
        default="https://spylang.github.io/spy",
        help="Base playground URL (default: https://spylang.github.io/spy)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        parser.error(f"File not found: {args.file}")

    url = create_snippet_url(args.file, args.url)
    print(url)


if __name__ == "__main__":
    main()
