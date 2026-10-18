"""
Build libspy variants on demand, in a cache directory.

For now this is used only for the host-dependent variants (native with
--march). Everything else is still built by `make -C spy/libspy`.
"""

import hashlib
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import py.path

import spy.libspy
from spy.build.build_info import BuildType, OutputKind
from spy.build.flags import (
    get_ar,
    get_build_dirname,
    get_cc,
    get_cflags,
    validate_march,
)
from spy.build.ninja import fmt_flags
from spy.errors import WIP

# same as SRCS in libspy/Makefile (without src/jsffi/jsffi.c, which is for
# emscripten only)
SRCS = [
    "src/str.c",
    "src/bytes.c",
    "src/builtins.c",
    "src/debug.c",
    "src/unsafe.c",
    "src/operator.c",
    "src/posix.c",
    "vendored/ryu/ryu/f2s.c",
    "vendored/ryu/ryu/d2s.c",
]

# see RYU_CFLAGS in libspy/Makefile
RYU_CFLAGS = ["-DRYU_FLOAT_FULL_TABLE", "-DRYU_ONLY_64_BIT_OPS"]


def get_ninja() -> list[str]:
    # `ninja` is not necessarily on PATH (e.g. `uv tool install`)
    return [sys.executable, "-m", "ninja"]


def variant_name(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> str:
    name = f"{target}/{get_build_dirname(build_type, kind)}"
    if march is not None:
        name += f"-march-{validate_march(march)}"
    return name


def get_cflags_for_variant(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> list[str]:
    libspy_dir = spy.libspy.BUILD.dirpath()
    ryu = ["-I", str(libspy_dir.join("vendored", "ryu"))] + RYU_CFLAGS
    return get_cflags(target, build_type, kind, False, march) + ryu


def cache_key(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> str:
    """
    Name of a build, computed from everything which influences it: if one of
    the inputs changes, the key changes, so that a stale libspy.a can never be
    reused by mistake.

    The inputs are the libspy sources and headers, the variant (target, build
    type, kind, march), the compiler version and the flags.
    """
    libspy_dir = spy.libspy.BUILD.dirpath()
    h = hashlib.sha256()
    for subdir in ("src", "include", "vendored"):
        for p in sorted(libspy_dir.join(subdir).visit(rec=True)):
            if p.check(file=True) and p.ext in (".c", ".h"):
                h.update(p.relto(libspy_dir).encode())
                h.update(p.read_binary())
    h.update(variant_name(target, build_type, kind, march).encode())
    h.update(" ".join(get_cflags_for_variant(target, build_type, kind, march)).encode())
    cc = get_cc(target).split()
    res = subprocess.run([*cc, "--version"], capture_output=True)
    h.update(res.stdout + res.stderr)
    return h.hexdigest()[:16]


def _gen_build_ninja(target: str, cflags: list[str]) -> str:
    libspy_dir = spy.libspy.BUILD.dirpath()
    lines = [
        f"cc = {get_cc(target)}",
        f"ar = {get_ar(target)}",
        f"cflags = {fmt_flags(cflags)}",
        "",
        "rule cc",
        "  command = $cc $cflags -MMD -MF $out.d -c $in -o $out",
        "  description = CC $out",
        "  depfile = $out.d",
        "  deps = gcc",
        "",
        "rule ar",
        "  command = $ar rcs $out $in",
        "  description = AR $out",
        "",
    ]
    objs = []
    for src in SRCS:
        obj = "obj/" + src[:-2] + ".o"
        objs.append(obj)
        lines.append(f"build {obj}: cc {libspy_dir.join(src)}")
    lines.append(f"build libspy.a: ar {fmt_flags(objs)}")
    lines.append("default libspy.a")
    return "\n".join(lines) + "\n"


def cache_dir() -> py.path.local:
    """
    Where the variants built by ensure_libspy() are stored, as
    <cache_dir>/<target>/<name>-<key>. The libspy built by `make` is not here.
    """
    return spy.libspy.BUILD.join("cache")


def clear_cache() -> int:
    """
    Delete all the variants built by ensure_libspy(). Return how many there
    were.
    """
    root = cache_dir()
    if not root.check(dir=True):
        return 0
    n = sum(
        len(target.listdir()) for target in root.listdir() if target.check(dir=True)
    )
    shutil.rmtree(root)
    return n


def ensure_libspy(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> py.path.local:
    """
    Return the directory containing libspy.a for this variant, building it
    first if it is not in the cache.
    """
    assert march is not None, "only the --march variants are built here for now"
    key = cache_key(target, build_type, kind, march)
    name = f"{get_build_dirname(build_type, kind)}-march-{march}-{key}"
    final = cache_dir().join(target, name)
    if final.join("libspy.a").check(file=True):
        return final

    # Build in a temporary directory, then rename it: a rename is atomic, so
    # nobody ever sees a half-built library, and several processes (e.g.
    # pytest-xdist workers) can start together without corrupting the cache.
    final.dirpath().ensure(dir=True)
    tmp = py.path.local(tempfile.mkdtemp(dir=str(final.dirpath())))
    try:
        cflags = get_cflags_for_variant(target, build_type, kind, march)
        tmp.join("build.ninja").write(_gen_build_ninja(target, cflags))
        subprocess.run([*get_ninja(), "-C", str(tmp)], check=True)
        if not tmp.join("libspy.a").check(file=True):
            raise WIP(f"ninja did not produce {final}/libspy.a")
        try:
            tmp.rename(final)
        except OSError:
            pass  # another process finished first
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final
