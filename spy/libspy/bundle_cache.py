"""
Content-addressed cache for WASM bundles produced by link_bundle().

Cache layout:
    <spy-root>/../build/wasm-bundles/<hash>/bundle.wasm
    <spy-root>/../build/wasm-bundles/<hash>/manifest.json

The cache key is a SHA-256 hash of:
- the content of each input .a archive
- the sorted list of exports
- the toolchain version (zig version string)

The cache lives project-local (next to the spy package root) so that
`git clean -fdx` cleans it along with other build artefacts, and so that
it stays aligned with the current checkout's libspy version.
"""

import hashlib
import json
import subprocess

import py.path

import spy
from spy.libspy.bundle import link_bundle

BUNDLE_CACHE_DIR = spy.ROOT.dirpath("build", "wasm-bundles")


def _zig_version() -> str:
    result = subprocess.run(
        ["python", "-m", "ziglang", "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _compute_cache_key(
    archives: list[py.path.local],
    exports: list[str],
) -> str:
    h = hashlib.sha256()
    for archive in archives:
        h.update(archive.read_binary())
    for export in sorted(exports):
        h.update(export.encode())
    h.update(_zig_version().encode())
    return h.hexdigest()


def get_or_build_bundle(
    archives: list[py.path.local],
    exports: list[str],
    *,
    force_rebuild: bool = False,
) -> py.path.local:
    """
    Return a cached WASM bundle for the given archives and exports,
    building it on first use.

    Args:
        archives:      list of .a archives to link (libspy.a first, then extras)
        exports:       WASM symbols to export from the bundle
        force_rebuild: bypass cache lookup and always rebuild
    """
    cache_key = _compute_cache_key(archives, exports)
    cache_dir = BUNDLE_CACHE_DIR.join(cache_key)
    bundle_path = cache_dir.join("bundle.wasm")
    manifest_path = cache_dir.join("manifest.json")

    if not force_rebuild and bundle_path.check(file=True):
        return bundle_path

    cache_dir.ensure(dir=True)
    link_bundle(archives, exports, out=bundle_path)

    manifest = {
        "archives": [str(a) for a in archives],
        "exports": sorted(exports),
        "zig_version": _zig_version(),
        "cache_key": cache_key,
    }
    manifest_path.write(json.dumps(manifest, indent=2))

    return bundle_path
