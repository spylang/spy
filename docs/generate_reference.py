"""
mkdocs hook: generate SPY_REFERENCE.md and SPY_EXAMPLES.md straight into the
built site (not as rendered doc pages) on every doc build.

Two self-contained Markdown files, generated from the existing docs/examples
so there's no risk of them drifting out of sync:

  - SPY_REFERENCE.md: the "how to" pages (language features) and the
    hand-written reference pages (builtins, types, `__spy__` module, env
    vars).

  - SPY_EXAMPLES.md: all the curated examples in
    examples/{1_high_level,2_metaprogramming,3_low_level,4_advanced},
    together with their expected output. These are the same examples used
    for the playground, and are designed to be sufficient on their own to
    get a good idea of the language.

Both are meant to be pasted (or pointed to) as context for an LLM working on
SPy code, which is why each needs to be a single file rather than a set of
linked pages. SPY_EXAMPLES.md alone should be enough for most day-to-day
development; SPY_REFERENCE.md fills in the less common corners.

They are dropped directly into the built site as plain files -- not routed
through mkdocs as doc pages -- since the point is the raw Markdown itself,
not a rendered HTML view of it; docs/src/index.md links to them directly.
Neither is versioned.

Generation happens via the mkdocs `hooks` mechanism (see mkdocs.yml)'s
`on_post_build`, so the files are (re)created on every `mkdocs build` /
`mkdocs serve`.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent  # .../docs
REPO_ROOT = DOCS_DIR.parent  # .../
SRC_DIR = DOCS_DIR / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"
EXPECTED_OUTPUT_DIR = EXAMPLES_DIR / "expected_output"

# Order matters: from simplest to most advanced.
EXAMPLE_DIRS = [
    ("1_high_level", "High-level features"),
    ("2_metaprogramming", "Metaprogramming"),
    ("3_low_level", "Low-level features (the `unsafe` module)"),
    ("4_advanced", "Advanced features and patterns"),
]

# Plain markdown pages to inline, relative to src/.
HOWTO_PAGES = [
    "howto/main_function.md",
    "howto/generics.md",
]

REFERENCE_PAGES = [
    "reference/python_builtins.md",
    "reference/spy_builtin_functions.md",
    "reference/builtin_types.md",
    "reference/spy_module.md",
    "reference/environment.md",
    # reference/cli.md is excluded: it's a mkdocs-typer2 directive, not plain
    # markdown, and doesn't render to anything useful outside a mkdocs build.
]

# mkdocs-material's attr_list syntax, e.g. "### foo() { data-toc-label='foo' }"
# or "### bar { #markdown data-toc-label='bar' }". Only used on heading lines
# in these docs, and only for TOC/anchor customization -- meaningless (and
# just noise) once inlined outside mkdocs.
_ATTR_LIST_RE = re.compile(r"^(#{1,6}\s+.*?)\s*\{[^{}\n]*\}\s*$", re.MULTILINE)


def _split_title(text: str) -> tuple[str | None, str]:
    """Split off a leading ``title: ...\\n---\\n`` header, used by some pages.

    Returns (title, remaining_body). If the page has no such header, title is
    None and the body is the page unchanged.
    """
    m = re.match(r"^title:\s*(.+?)\s*\n---\s*\n+", text)
    if m:
        return m.group(1), text[m.end() :]
    return None, text


def _fix_relative_links(body: str, rel_path: str) -> str:
    """Rewrite links so they still resolve once inlined at the top level.

    `rel_path` is e.g. "howto/main_function.md" -- one directory below src/.
    A link like `](../reference/foo.md)` written from that directory needs
    to become `](reference/foo.md)` once the text lives directly in the
    top-level SPY_REFERENCE.md.
    """
    depth = rel_path.count("/")
    prefix = "../" * depth
    if not prefix:
        return body
    return body.replace(f"]({prefix}", "](")


def _strip_attr_list(body: str) -> str:
    return _ATTR_LIST_RE.sub(r"\1", body)


def _read_page(rel_path: str) -> str:
    text = (SRC_DIR / rel_path).read_text()
    title, body = _split_title(text)
    body = _fix_relative_links(body, rel_path)
    body = _strip_attr_list(body)
    if title is None:
        # e.g. index.md, which already starts with its own "# Heading"
        return body.rstrip() + "\n"
    return f"## {title}\n\n{body.rstrip()}\n"


def _render_example(spy_file: Path) -> str:
    rel = spy_file.relative_to(EXAMPLES_DIR)
    source = spy_file.read_text().rstrip("\n")
    parts = [f"### `{rel}`\n", "```python", source, "```"]

    expected_file = EXPECTED_OUTPUT_DIR / f"{spy_file.stem}.txt"
    if expected_file.exists():
        output = expected_file.read_text().rstrip("\n")
        parts += ["", "Output:", "```", output, "```"]

    return "\n".join(parts) + "\n"


def generate_reference() -> str:
    # Plain markdown only: this file is meant to be read raw (pasted into a
    # prompt, fetched by a tool), not rendered by mkdocs, so no mkdocs-only
    # extension syntax (admonitions, buttons, ...) here.
    chunks = [
        "# SPy reference\n",
        "> Generated automatically from `docs/src/howto/` and "
        "`docs/src/reference/`. Do not edit by hand -- see "
        "docs/generate_reference.py.\n",
        "Language-feature docs and reference docs concatenated into one "
        "place, meant to be used as context for LLM-assisted development on "
        "SPy. For working code, see [SPy examples](SPY_EXAMPLES.md).\n",
        "## Language features\n",
    ]

    for rel_path in HOWTO_PAGES:
        chunks.append(_read_page(rel_path))

    chunks.append("## Reference\n")
    for rel_path in REFERENCE_PAGES:
        chunks.append(_read_page(rel_path))

    return "\n".join(chunks)


def generate_examples() -> str:
    chunks = [
        "# SPy examples\n",
        "> Generated automatically from `examples/`. Do not edit by hand -- "
        "see docs/generate_reference.py.\n",
        "All the curated examples under `examples/`, together with their "
        "expected output, concatenated into one place. This is meant to be "
        "used as context for LLM-assisted development on SPy. For less "
        "common corners of the language, see the "
        "[SPy reference](SPY_REFERENCE.md).\n",
    ]

    for dirname, description in EXAMPLE_DIRS:
        chunks.append(f"## {dirname} — {description}\n")
        spy_files = sorted((EXAMPLES_DIR / dirname).glob("*.spy"))
        for spy_file in spy_files:
            chunks.append(_render_example(spy_file))

    return "\n".join(chunks)


# --- mkdocs hooks -----------------------------------------------------------


def on_post_build(config, **kwargs):
    site_dir = Path(config["site_dir"])
    (site_dir / "SPY_REFERENCE.md").write_text(generate_reference())
    (site_dir / "SPY_EXAMPLES.md").write_text(generate_examples())


def on_serve(server, config, builder, **kwargs):
    # Rebuild also when the sources that feed these files change, even
    # though they live outside docs_dir (mkdocs only watches docs_dir by
    # default).
    server.watch(str(EXAMPLES_DIR), builder)
    for rel_path in HOWTO_PAGES + REFERENCE_PAGES:
        server.watch(str(SRC_DIR / rel_path), builder)
    return server


if __name__ == "__main__":
    # Handy for manual testing: `python docs/generate_reference.py`. Mirrors
    # the real build's output location (docs/site, already gitignored).
    out_dir = DOCS_DIR / "site"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "SPY_REFERENCE.md").write_text(generate_reference())
    (out_dir / "SPY_EXAMPLES.md").write_text(generate_examples())
    print(f"wrote {out_dir / 'SPY_REFERENCE.md'}")
    print(f"wrote {out_dir / 'SPY_EXAMPLES.md'}")
