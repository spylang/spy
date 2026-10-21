"""
Build libspy variants, and find them at run time.

A variant is (target, build type, kind, march). ensure_libspy() returns the
directory containing its libspy.a (plus libspy.wasm/libspy.mjs where relevant):

  1. a prebuilt variant shipped in the wheel (spy/libspy/prebuilt), if any;
  2. else a build in the user cache, built on first use.

Importing this module must not need wasmtime: the build hook uses it.
"""

import argparse
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import platformdirs
import py.path

import spy.libspy
from spy.build.build_info import BuildType, OutputKind
from spy.build.flags import (
    fmt_flags,
    get_ar,
    get_build_dirname,
    get_cc,
    get_cflags,
    get_ninja,
    validate_march,
)
from spy.errors import WIP

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

# RYU_FLOAT_FULL_TABLE makes f2s use its dedicated binary32 powers-of-five
# tables instead of depending on the larger d2s tables.
#
# RYU_ONLY_64_BIT_OPS disables d2s's __uint128_t path. Zig lowers those
# operations to compiler runtime helpers whose signatures conflict under the
# WASM multivalue ABI, so use Ryu's portable 64-bit implementation instead.
RYU_CFLAGS = ["-DRYU_FLOAT_FULL_TABLE", "-DRYU_ONLY_64_BIT_OPS"]

# the variants built by `python -m spy.libspy.builder`
STANDARD_VARIANTS = [
    ("native", "release", "exe"),
    ("native", "debug", "exe"),
    ("native-static", "release", "exe"),
    ("native-static", "debug", "exe"),
    ("wasi", "release", "exe"),
    ("wasi", "debug", "exe"),
    ("wasi", "debug", "testlib"),
    ("emscripten", "release", "exe"),
    ("emscripten", "debug", "exe"),
    ("emscripten", "debug", "testlib"),
]

# the only variant shipped in the wheel: it is portable (wasm) and it is the
# one used by the interpreter
PREBUILT_VARIANT = ("wasi", "debug", "testlib")


def get_srcs(target: str) -> list[str]:
    if target == "emscripten":
        return SRCS + ["src/jsffi/jsffi.c"]
    return SRCS


def variant_name(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> str:
    return f"{target}/{_dirname(build_type, kind, march)}"


def _dirname(build_type: BuildType, kind: OutputKind, march: Optional[str]) -> str:
    name = get_build_dirname(build_type, kind)
    if march is not None:
        name += f"-march-{validate_march(march)}"
    return name


def get_cflags_for_variant(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str]
) -> list[str]:
    ryu = ["-I", str(spy.libspy.ROOT.join("vendored", "ryu"))] + RYU_CFLAGS
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
    libspy_dir = spy.libspy.ROOT
    h = hashlib.sha256()
    for subdir in ("src", "include", "vendored"):
        for p in sorted(libspy_dir.join(subdir).visit(rec=True)):
            if p.check(file=True) and p.ext in (".c", ".h"):
                h.update(p.relto(libspy_dir).encode())
                h.update(p.read_binary())
    h.update(variant_name(target, build_type, kind, march).encode())
    h.update(" ".join(get_cflags_for_variant(target, build_type, kind, march)).encode())
    cc = shlex.split(get_cc(target))
    res = subprocess.run([*cc, "--version"], capture_output=True)
    h.update(res.stdout + res.stderr)
    return h.hexdigest()[:16]


# how to link libspy.a into a loadable module. wasi: only testlibs, which are
# loaded by the interpreter (a reactor, i.e. a library without main, with the
# whole libspy.a so that all functions are available to the host).
_LINK_RULES = {
    "wasi": (
        "libspy.wasm",
        "$cc --target=wasm32-wasi-musl -mexec-model=reactor "
        "-Wl,--whole-archive $in -o $out",
    ),
    "emscripten": (
        "libspy.mjs",
        "$cc -sWASM_BIGINT -sEXPORTED_RUNTIME_METHODS=HEAP8 "
        "-Wl,--whole-archive $in -o $out",
    ),
}


def _gen_build_ninja(target: str, cflags: list[str], kind: OutputKind = "exe") -> str:
    libspy_dir = spy.libspy.ROOT
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
    if target in _LINK_RULES:
        lines += [
            "rule link",
            f"  command = {_LINK_RULES[target][1]}",
            "  description = LINK $out",
            "",
        ]
    objs = []
    for src in get_srcs(target):
        obj = "obj/" + src[:-2] + ".o"
        objs.append(obj)
        lines.append(f"build {obj}: cc {libspy_dir.join(src)}")
    lines.append(f"build libspy.a: ar {fmt_flags(objs)}")
    default = "libspy.a"
    if target == "emscripten":
        # emcc also writes libspy.wasm next to the .mjs
        lines.append("build libspy.mjs | libspy.wasm: link libspy.a")
        default = "libspy.mjs"
    elif target == "wasi" and kind == "testlib":
        lines.append("build libspy.wasm: link libspy.a")
        default = "libspy.wasm"
    lines.append(f"default {default}")
    return "\n".join(lines) + "\n"


# how many builds are kept for each variant, see prune_cache()
KEEP_PER_VARIANT = 3

# <build type>-march-<march>-<key>, see ensure_libspy()
_BUILD_DIRNAME = re.compile(r"(?P<variant>.+)-[0-9a-f]{16}")


def cache_root() -> py.path.local:
    """
    The user cache directory of SPy: $SPY_CACHE_DIR if it is set, else the
    standard one of the platform (~/.cache/spy on Linux, honoring
    $XDG_CACHE_HOME).
    """
    env = os.environ.get("SPY_CACHE_DIR")
    if env:
        return py.path.local(env)
    return py.path.local(platformdirs.user_cache_dir("spy"))


def cache_dir() -> py.path.local:
    """
    Where the variants built by ensure_libspy() are stored, as
    <cache_dir>/<target>/<name>-<key>. The libspy built by `make` is not here.
    """
    return cache_root().join("libspy")


def _mtime(path: py.path.local) -> float:
    try:
        return path.mtime()
    except OSError:  # removed by another process
        return 0.0


def prune_cache(keep: int = KEEP_PER_VARIANT) -> int:
    """
    For each variant (same target, build type, kind and march, whatever the
    key), keep only the `keep` most recently used builds and delete the others.
    Return how many were deleted.
    """
    removed = 0
    root = cache_dir()
    if not root.check(dir=True):
        return 0
    for target in root.listdir():
        variants: dict[str, list[py.path.local]] = {}
        for d in target.listdir():
            m = _BUILD_DIRNAME.fullmatch(d.basename)
            if m and d.check(dir=True):
                variants.setdefault(m["variant"], []).append(d)
        for builds in variants.values():
            builds.sort(key=_mtime, reverse=True)
            for old in builds[keep:]:
                shutil.rmtree(old, ignore_errors=True)
                removed += 1
    return removed


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


def _touch(path: py.path.local) -> None:
    """Record that this build has just been used."""
    try:
        os.utime(path)
    except OSError:
        pass


def _find_prebuilt(
    target: str, build_type: BuildType, kind: OutputKind
) -> Optional[py.path.local]:
    d = spy.libspy.PREBUILT.join(target, get_build_dirname(build_type, kind))
    if d.join("libspy.a").check(file=True):
        return d
    return None


def build_variant(
    target: str,
    build_type: BuildType,
    kind: OutputKind,
    march: Optional[str],
    dest: py.path.local,
) -> None:
    """
    Build a variant into the directory `dest`, which must not exist. The build
    happens in a temporary sibling directory which is then renamed: a rename is
    atomic, so nobody ever sees a half-built library, and several processes
    (e.g. pytest-xdist workers) can start together without corrupting the
    cache. If the rename fails, another process finished first.
    """
    dest.dirpath().ensure(dir=True)
    tmp = py.path.local(tempfile.mkdtemp(dir=str(dest.dirpath())))
    try:
        cflags = get_cflags_for_variant(target, build_type, kind, march)
        tmp.join("build.ninja").write(_gen_build_ninja(target, cflags, kind))
        subprocess.run([*get_ninja(), "-C", str(tmp)], check=True)
        if not tmp.join("libspy.a").check(file=True):
            raise WIP(f"ninja did not produce {dest}/libspy.a")
        try:
            tmp.rename(dest)
        except OSError:
            pass  # another process finished first
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ensure_libspy(
    target: str, build_type: BuildType, kind: OutputKind, march: Optional[str] = None
) -> py.path.local:
    """
    Return the directory containing libspy.a for this variant: the prebuilt one
    shipped in the wheel if there is one, else a build in the cache, which is
    built first if needed.
    """
    if march is None:
        prebuilt = _find_prebuilt(target, build_type, kind)
        if prebuilt is not None:
            return prebuilt
    key = cache_key(target, build_type, kind, march)
    final = cache_dir().join(target, f"{_dirname(build_type, kind, march)}-{key}")
    if final.join("libspy.a").check(file=True):
        _touch(final)
        return final
    build_variant(target, build_type, kind, march, final)
    prune_cache()
    return final


def build_standard_variants() -> None:
    """Fill the cache with the standard variants (see `make -C spy/libspy`)."""
    for target, build_type, kind in STANDARD_VARIANTS:
        if target == "emscripten" and shutil.which("emcc") is None:
            continue
        if target == "native-static" and sys.platform == "darwin":
            continue
        if target == "native" and shutil.which("cc") is None:
            continue
        ensure_libspy(target, build_type, kind, None)  # type: ignore[arg-type]


def build_prebuilt(dest: py.path.local) -> None:
    """
    Build the variants shipped in the wheel into `dest`, as
    <dest>/<target>/<build type>[-testlib]/libspy.{a,wasm}.
    """
    target, build_type, kind = PREBUILT_VARIANT
    out = dest.join(target, get_build_dirname(build_type, kind))  # type: ignore[arg-type]
    if out.check():
        shutil.rmtree(out)
    build_variant(target, build_type, kind, None, out)  # type: ignore[arg-type]
    # keep only what is used at run time, not the ninja files and the objects
    for p in out.listdir():
        if p.basename not in ("libspy.a", "libspy.wasm"):
            shutil.rmtree(p) if p.check(dir=True) else p.remove()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build libspy into the cache. Without arguments, build all "
        "the standard variants. With --target, build one variant and print "
        "its directory."
    )
    parser.add_argument("--target")
    parser.add_argument("--build-type", default="debug")
    parser.add_argument("--output-kind", default="exe")
    parser.add_argument("--march")
    args = parser.parse_args(argv)
    if args.target is None:
        build_standard_variants()
    else:
        # the build output goes to stderr, so that stdout contains only the
        # directory (e.g. to be used as `$(python -m spy.libspy.builder ...)`)
        sys.stdout.flush()
        saved = os.dup(1)
        os.dup2(2, 1)
        try:
            libdir = ensure_libspy(
                args.target, args.build_type, args.output_kind, args.march
            )
        finally:
            os.dup2(saved, 1)
            os.close(saved)
        print(libdir)


if __name__ == "__main__":
    main()
