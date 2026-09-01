"""
CLI helper that prints compiler flags for building out-of-tree modules
against libspy.

Usage:
    python -m spy.build.flags --cflags --target=wasi --build-type=debug
    python -m spy.build.flags --ldflags --target=wasi --build-type=release
    python -m spy.build.flags --libdir --target=wasi --build-type=debug
    python -m spy.build.flags --cc --target=wasi
    python -m spy.build.flags --cflags --target=wasi --output-kind=testlib
"""

import argparse
import sys
from os import getenv
from typing import Optional

import spy
from spy.build.build_info import BuildType, OutputKind

_LIBSPY = spy.ROOT.join("libspy")
_INCLUDE = _LIBSPY.join("include")
_BUILD = _LIBSPY.join("build")


# Base CFLAGS shared by all targets (mirrors spy/libspy/Makefile)
_BASE_CFLAGS: list[str] = [
    "-fvisibility=hidden",
    "-fPIC",
    "-DSPY_GC_NONE",
]

# WASM-specific CFLAGS shared by wasi and emscripten
_WASM_CFLAGS: list[str] = [
    "-mmultivalue",
    "-Xclang",
    "-target-abi",
    "-Xclang",
    "experimental-mv",
    "-mbulk-memory",
]

_TARGET_CFLAGS: dict[str, list[str]] = {
    "wasi": [
        "-DSPY_TARGET_WASI",
        "--target=wasm32-wasi-musl",
        *_WASM_CFLAGS,
    ],
    "emscripten": [
        "-DSPY_TARGET_EMSCRIPTEN",
        *_WASM_CFLAGS,
    ],
    "native": [
        "-DSPY_TARGET_NATIVE",
    ],
    "native-static": [
        "-DSPY_TARGET_NATIVE",
        "--target=native-native-musl",
    ],
}

_TARGET_LDFLAGS: dict[str, list[str]] = {
    "wasi": [
        "--target=wasm32-wasi-musl",
    ],
    "emscripten": [],
    "native": [],
    "native-static": [
        "--target=native-native-musl",
        "-static",
    ],
}

_OUTPUT_KIND_CFLAGS: dict[str, list[str]] = {
    "exe": ["-DSPY_OUTPUT_KIND_EXE"],
    "testlib": ["-DSPY_OUTPUT_KIND_TESTLIB"],
    "py-cffi": ["-DSPY_OUTPUT_KIND_PY_CFFI"],
}

_WARNING_CFLAGS: list[str] = ["-Werror=implicit-function-declaration"]
_WARNING_AS_ERROR_CFLAGS: list[str] = ["-Werror", "-Wno-unreachable-code"]

_BUILD_TYPE_CFLAGS: dict[str, list[str]] = {
    "release": ["-DSPY_RELEASE", "-O3", "-flto"],
    "debug": ["-DSPY_DEBUG", "-O0", "-g"],
}

_BUILD_TYPE_LDFLAGS: dict[str, list[str]] = {
    "release": ["-flto"],
    "debug": [],
}

_TARGET_CC: dict[str, str] = {
    "wasi": "python -m ziglang cc",
    "emscripten": "emcc",
    "native": "cc",
    "native-static": "python -m ziglang cc",
}

_TARGET_AR: dict[str, str] = {
    "wasi": "python -m ziglang ar",
    "emscripten": "emar",
    "native": "ar",
    "native-static": "python -m ziglang ar",
}


def _check_target(target: str) -> None:
    if target not in _TARGET_CFLAGS:
        raise ValueError(f"Unknown target: {target!r}. Valid: {list(_TARGET_CFLAGS)}")


def _check_build_type(build_type: str) -> None:
    if build_type not in _BUILD_TYPE_CFLAGS:
        raise ValueError(
            f"Unknown build_type: {build_type!r}. Valid: {list(_BUILD_TYPE_CFLAGS)}"
        )


def _check_output_kind(output_kind: str) -> None:
    if output_kind not in _OUTPUT_KIND_CFLAGS:
        raise ValueError(
            f"Unknown output_kind: {output_kind!r}. Valid: {list(_OUTPUT_KIND_CFLAGS)}"
        )


def get_cflags(
    target: str,
    build_type: BuildType,
    output_kind: OutputKind = "exe",
    warning_as_error: bool = False,
    march: Optional[str] = None,
) -> list[str]:
    _check_target(target)
    _check_build_type(build_type)
    _check_output_kind(output_kind)
    if warning_as_error or getenv("SPY_WERROR") in ("true", "1"):
        warning_flags = _WARNING_AS_ERROR_CFLAGS
    else:
        warning_flags = _WARNING_CFLAGS
    include = ["-I", str(_INCLUDE)]
    march_flags = [f"-march={march}"] if march is not None else []
    return (
        _BASE_CFLAGS
        + _TARGET_CFLAGS[target]
        + _BUILD_TYPE_CFLAGS[build_type]
        + _OUTPUT_KIND_CFLAGS[output_kind]
        + warning_flags
        + include
        + march_flags
    )


def get_ldflags(target: str, build_type: BuildType) -> list[str]:
    _check_target(target)
    _check_build_type(build_type)
    return _TARGET_LDFLAGS[target] + _BUILD_TYPE_LDFLAGS[build_type]


def _sanitize_march(march: str) -> str:
    """
    Turn a -march value into something safe to use as a single path
    component (e.g. "native" -> "native", "x86-64-v3" -> "x86-64-v3").
    Conservative: anything that isn't alphanumeric/./-/+/_ gets replaced.
    """
    return "".join(c if c.isalnum() or c in "-._+" else "_" for c in march)


def get_build_dirname(
    build_type: BuildType,
    output_kind: OutputKind = "exe",
    march: Optional[str] = None,
) -> str:
    """
    Name of the libspy build dir for the given flavor, e.g. 'debug' or
    'debug-testlib'.

    testlibs need their own libspy.a, which expects the host to provide the
    debug helpers instead of implementing them in debug.c.

    If march is given, it is appended as a suffix (e.g. 'release-march-native')
    so that different -march values get their own cached libspy.a instead of
    silently linking a module against a libspy.a built for a different ISA
    (see issue: --march mismatch between the module and libspy.a).
    """
    _check_build_type(build_type)
    _check_output_kind(output_kind)
    if output_kind == "testlib":
        name = f"{build_type}-testlib"
    else:
        name = build_type
    if march is not None:
        name += f"-march-{_sanitize_march(march)}"
    return name


def get_libdir(
    target: str,
    build_type: BuildType,
    output_kind: OutputKind = "exe",
    march: Optional[str] = None,
) -> str:
    _check_target(target)
    return str(_BUILD.join(target, get_build_dirname(build_type, output_kind, march)))


def get_cc(target: str) -> str:
    _check_target(target)
    return _TARGET_CC[target]


def get_ar(target: str) -> str:
    _check_target(target)
    return _TARGET_AR[target]


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print compiler flags for building out-of-tree libspy modules"
    )
    parser.add_argument(
        "--target",
        choices=list(_TARGET_CFLAGS),
        help="Build target",
    )
    parser.add_argument(
        "--build-type",
        choices=list(_BUILD_TYPE_CFLAGS),
        default="debug",
        help="Build type (default: debug)",
    )
    parser.add_argument(
        "--output-kind",
        choices=list(_OUTPUT_KIND_CFLAGS),
        default="exe",
        help="Output kind (default: exe)",
    )
    parser.add_argument(
        "--warning-as-error",
        action="store_true",
        help="Treat warnings as errors (overrides SPY_WERROR env var)",
    )
    parser.add_argument(
        "--march",
        default=None,
        help="Value for -march=<VALUE> (e.g. 'native'); also used to pick "
        "a dedicated libspy build dir so it never gets mixed up with a "
        "libspy.a built for a different ISA",
    )
    parser.add_argument(
        "--cflags",
        action="store_true",
        help="Print CFLAGS (requires --target)",
    )
    parser.add_argument(
        "--ldflags",
        action="store_true",
        help="Print LDFLAGS (requires --target)",
    )
    parser.add_argument(
        "--libdir",
        action="store_true",
        help="Print the libspy build directory (-L path, requires --target)",
    )
    parser.add_argument(
        "--cc",
        action="store_true",
        help="Print the C compiler for the given target (requires --target)",
    )
    parser.add_argument(
        "--ar",
        action="store_true",
        help="Print the archiver for the given target (requires --target)",
    )
    args = parser.parse_args(argv)

    parts: list[str] = []

    if args.cflags:
        if not args.target:
            print("error: --cflags requires --target", file=sys.stderr)
            sys.exit(1)
        parts += get_cflags(
            args.target,
            args.build_type,
            args.output_kind,
            args.warning_as_error,
            args.march,
        )

    if args.ldflags:
        if not args.target:
            print("error: --ldflags requires --target", file=sys.stderr)
            sys.exit(1)
        parts += get_ldflags(args.target, args.build_type)

    if args.libdir:
        if not args.target:
            print("error: --libdir requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(
            f"-L{get_libdir(args.target, args.build_type, args.output_kind, args.march)}"
        )

    if args.cc:
        if not args.target:
            print("error: --cc requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(get_cc(args.target))

    if args.ar:
        if not args.target:
            print("error: --ar requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(get_ar(args.target))

    if parts:
        print(" ".join(parts))


if __name__ == "__main__":
    main()
