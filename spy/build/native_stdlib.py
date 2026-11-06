"""
PROTOTYPE: prebuild some stdlib modules into a wasm32-wasi .a archive, so that
the interpreter can call the compiled functions instead of interpreting them.

The archive is linked together with libspy.a into the VM's WASM instance (see
spy.libspy.get_LLMOD), so that interpreted and compiled code share the same
linear memory.

Everything is derived from the C backend: we redshift the requested modules,
let CBackend emit them, and read the *manifest* off the objects it emitted:

  - functions: red, non-@force_inline W_ASTFuncs of the requested modules,
    whose signature we know how to marshal;
  - cells: the module-level variables of every emitted module, because the
    compiled code of any of them may read or write the C global.

The manifest is stored as JSON next to the archive. It is used to generate the
export shims (the C side) and the NativeRegistry (the interpreter side).
"""

import functools
import hashlib
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import py.path

import spy
from spy.build.wasm_bundle import BUNDLE_CACHE_DIR, _zig_version
from spy.fqn import FQN
from spy.vm.object import W_Type

STDLIB = spy.ROOT.join("..", "stdlib")
LIBSPY_INCLUDE = spy.ROOT.join("libspy", "include")
DEFAULT_MODULES = ("random",)
STUB_NAME = "_native_stub"
MANIFEST_VERSION = 1


def scalar_types() -> list[W_Type]:
    """
    SPy types which we know how to pass through a wasm call, as parameters and
    as results. NoneType is allowed only as a result.

    This is a function because the builtin types exist only after spy.vm.vm
    has been imported.
    """
    from spy.vm.b import B

    return [B.w_i32, B.w_u32, B.w_f64, B.w_f32, B.w_bool, B.w_str]


def result_types() -> list[W_Type]:
    from spy.vm.b import TYPES

    return scalar_types() + [TYPES.w_NoneType]


def type_name(w_T: W_Type) -> str:
    return str(w_T.fqn)


@dataclass
class NativeFunc:
    fqn: str  # e.g. "random::seed"
    export: str  # name of the WASM export
    c_name: str  # name of the function emitted by the C backend
    header: str  # .h which declares it
    params: list[str]  # SPy type names
    restype: str
    c_params: list[str]  # the same, as C types
    c_restype: str


@dataclass
class NativeCell:
    fqn: str  # e.g. "_random::_ptr_global_random"
    export: str  # WASM export returning the ADDRESS of the C global
    c_name: str  # name of the C global
    header: str
    kind: str  # "i32" or "ptr"
    type: str  # SPy type name


@dataclass
class Skipped:
    fqn: str
    reason: str


@dataclass
class Manifest:
    version: int
    modules: list[str]
    funcs: list[NativeFunc] = field(default_factory=list)
    cells: list[NativeCell] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)

    def dump(self, path: py.path.local) -> None:
        path.write(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: py.path.local) -> "Manifest":
        d = json.loads(path.read())
        if d["version"] != MANIFEST_VERSION:
            raise ValueError(f"unsupported manifest version: {d['version']}")
        return cls(
            version=d["version"],
            modules=d["modules"],
            funcs=[NativeFunc(**f) for f in d["funcs"]],
            cells=[NativeCell(**c) for c in d["cells"]],
            skipped=[Skipped(**s) for s in d["skipped"]],
        )

    def gen_shim(self) -> str:
        """
        Generate the C file which exports the functions and the addresses of
        the globals under simple names.
        """
        headers = sorted(
            {f.header for f in self.funcs} | {c.header for c in self.cells}
        )
        lines = ['#include "spy.h"']
        lines += [f'#include "{h}"' for h in headers]
        lines.append("")
        for f in self.funcs:
            params = ", ".join(f"{t} a{i}" for i, t in enumerate(f.c_params))
            args = ", ".join(f"a{i}" for i in range(len(f.c_params)))
            ret = "" if f.c_restype == "void" else "return "
            lines.append(
                f"{f.c_restype} WASM_EXPORT({f.export})({params or 'void'}) "
                f"{{ {ret}{f.c_name}({args}); }}"
            )
        for c in self.cells:
            # a data symbol cannot be exported portably: export its address
            lines.append(
                f"void *WASM_EXPORT({c.export})(void) {{ return &{c.c_name}; }}"
            )
        return "\n".join(lines) + "\n"


@dataclass
class NativeStdlib:
    archive: py.path.local
    manifest: Manifest


# ======================= manifest generation =======================


def _export_name(c_name: str, used: set[str]) -> str:
    assert re.fullmatch(r"[A-Za-z0-9_$]+", c_name), c_name
    name = "native_" + c_name.replace("$", "__")
    assert name not in used, f"duplicate export name: {name}"
    used.add(name)
    return name


def _is_plain(fqn: FQN) -> bool:
    """
    Generic instantiations and closures have qualifiers or a suffix: we cannot
    be sure that the interpreter will name them in the same way.
    """
    return all(not p.qualifiers and not p.suffix for p in fqn.parts)


def generate(
    modnames: tuple[str, ...], path: tuple[str, ...], gen_dir: py.path.local
) -> Manifest:
    """
    Redshift `modnames`, emit the C code into gen_dir/src, and return the
    manifest of what was emitted.
    """
    from spy.analyze.importing import ImportAnalyzer
    from spy.backend.c.cbackend import CBackend
    from spy.backend.c.context import Context
    from spy.build.config import BuildConfig
    from spy.vm.cell import W_Cell
    from spy.vm.function import W_ASTFunc
    from spy.vm.modules.unsafe.ptr import W_Ptr, W_PtrType
    from spy.vm.primitive import W_I32
    from spy.vm.vm import SPyVM

    gen_dir.ensure(dir=True)
    stub = gen_dir.join(f"{STUB_NAME}.spy")
    stub.write(
        "".join(f"import {m}\n" for m in modnames) + "\ndef main() -> None:\n    pass\n"
    )

    # NOTE: native_stdlib=False, else we would recurse
    vm = SPyVM(native_stdlib=False)
    for p in (*path, str(gen_dir)):
        vm.path.append(p)
    importer = ImportAnalyzer(vm, STUB_NAME, use_spyc=False)
    importer.astcompile_all()
    importer.import_all()
    vm.ast_color_map = {}
    vm.redshift(error_mode="eager")

    config = BuildConfig(target="wasi", kind="exe", build_type="debug")
    backend = CBackend(vm, STUB_NAME, config, gen_dir, dump_c=False)
    backend.cwrite()

    ctx = Context(vm)
    manifest = Manifest(version=MANIFEST_VERSION, modules=list(modnames))
    used: set[str] = set()
    for modname, c_mod in backend.c_modules.items():
        if modname == STUB_NAME:
            continue
        header = c_mod.hfile.basename
        for fqn, w_obj in c_mod.content:
            if isinstance(w_obj, W_ASTFunc):
                # same condition used by CModuleWriter.emit_obj
                if w_obj.color != "red" or w_obj.is_force_inline:
                    continue
                if modname not in modnames:
                    continue
                reason = _unsupported_reason(fqn, w_obj)
                if reason is not None:
                    manifest.skipped.append(Skipped(str(fqn), reason))
                    continue
                w_ft = w_obj.w_functype
                manifest.funcs.append(
                    NativeFunc(
                        fqn=str(fqn),
                        export=_export_name(fqn.c_name, used),
                        c_name=fqn.c_name,
                        header=header,
                        params=[type_name(p.w_T) for p in w_ft.params],
                        restype=type_name(w_ft.w_restype),
                        c_params=[str(ctx.w2c(p.w_T)) for p in w_ft.params],
                        c_restype=str(ctx.w2c(w_ft.w_restype)),
                    )
                )
            elif isinstance(w_obj, W_Cell):
                w_val = w_obj.get()
                w_T = vm.dynamic_type(w_val)
                if isinstance(w_val, W_I32):
                    kind = "i32"
                elif isinstance(w_val, W_Ptr) and isinstance(w_T, W_PtrType):
                    kind = "ptr"
                else:
                    manifest.skipped.append(
                        Skipped(str(fqn), f"variable of type {w_T.fqn}")
                    )
                    continue
                manifest.cells.append(
                    NativeCell(
                        fqn=str(fqn),
                        export=_export_name(fqn.c_name, used),
                        c_name=fqn.c_name,
                        header=header,
                        kind=kind,
                        type=type_name(w_T),
                    )
                )
    return manifest


def _unsupported_reason(fqn: FQN, w_func: Any) -> Optional[str]:
    if not _is_plain(fqn):
        return "generic instantiation or closure"
    w_ft = w_func.w_functype
    for p in w_ft.params:
        if p.kind != "simple":
            return "variadic parameters"
        if p.w_T not in scalar_types():
            return f"parameter of type {type_name(p.w_T)}"
    if w_ft.w_restype not in result_types():
        return f"result of type {type_name(w_ft.w_restype)}"
    return None


# ======================= archive build and cache =======================


def _cflags() -> list[str]:
    out = subprocess.run(
        [
            sys.executable, "-m", "spy.build.flags", "--cflags",
            "--target=wasi", "--build-type=debug", "--output-kind=testlib",
        ],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return shlex.split(out)


def build_archive(
    modnames: tuple[str, ...], path: tuple[str, ...], out_dir: py.path.local
) -> Manifest:
    gen = out_dir.join("gen")
    manifest = generate(modnames, path, gen)
    src = gen.join("src")
    src.join("native_shim.c").write(manifest.gen_shim())

    # compile everything but the stub's own module (which has main())
    cflags = _cflags() + [f"-I{src}"]
    cfiles = [c for c in sorted(src.listdir("*.c")) if c.purebasename != STUB_NAME]
    objs = []
    procs = []
    for c in cfiles:
        o = c.new(ext=".o")
        objs.append(o)
        cmd = [
            sys.executable,
            "-m",
            "ziglang",
            "cc",
            *cflags,
            "-c",
            str(c),
            "-o",
            str(o),
        ]
        procs.append((c, subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)))
    for c, p in procs:
        _, err = p.communicate()
        if p.returncode != 0:
            raise RuntimeError(f"cannot compile {c}:\n{err}")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "ziglang",
            "ar",
            "rcs",
            str(out_dir.join("libspy_stdlib.a")),
        ]
        + [str(o) for o in objs],
        check=True,
    )
    manifest.dump(out_dir.join("manifest.json"))
    return manifest


def _compiler_hash() -> str:
    """
    Hash of the sources of the SPy compiler: if they change, the generated C
    (and thus the manifest) may change.
    """
    h = hashlib.sha256()
    skip = {"tests", "__pycache__", "vendored"}
    for f in sorted(spy.ROOT.visit("*.py", rec=lambda p: p.basename not in skip)):
        h.update(f.read_binary())
    return h.hexdigest()


def _cache_key(modnames: tuple[str, ...], path: tuple[str, ...]) -> str:
    h = hashlib.sha256()
    h.update(repr(modnames).encode())
    for d in [STDLIB, *map(py.path.local, path)]:
        for f in sorted(d.listdir("*.spy")):
            h.update(f.basename.encode())
            h.update(f.read_binary())
    for f in sorted(LIBSPY_INCLUDE.visit("*.h")):
        h.update(f.read_binary())
    h.update(_compiler_hash().encode())
    h.update(_zig_version().encode())
    return h.hexdigest()


@functools.lru_cache(maxsize=None)
def _get_native_stdlib(
    modnames: tuple[str, ...], path: tuple[str, ...]
) -> NativeStdlib:
    out_dir = BUNDLE_CACHE_DIR.join("native-stdlib", _cache_key(modnames, path))
    archive = out_dir.join("libspy_stdlib.a")
    manifest_file = out_dir.join("manifest.json")
    if archive.check(file=True) and manifest_file.check(file=True):
        return NativeStdlib(archive, Manifest.load(manifest_file))
    out_dir.ensure(dir=True)
    manifest = build_archive(modnames, path, out_dir)
    return NativeStdlib(archive, manifest)


def get_native_stdlib(
    modnames: tuple[str, ...] = DEFAULT_MODULES, path: tuple[str, ...] = ()
) -> NativeStdlib:
    """
    Return the (cached) archive and manifest of the prebuilt modules.

    `path` is the list of extra directories where to look for the modules, in
    addition to the stdlib.
    """
    return _get_native_stdlib(tuple(modnames), tuple(str(p) for p in path))


def main() -> None:
    modnames = tuple(sys.argv[1:]) or DEFAULT_MODULES
    nsl = get_native_stdlib(modnames)
    m = nsl.manifest
    print(f"archive: {nsl.archive}")
    print(f"modules: {', '.join(m.modules)}")
    print("native functions:")
    for f in m.funcs:
        print(f"  {f.fqn}({', '.join(f.params)}) -> {f.restype}   [{f.export}]")
    print("native variables:")
    for c in m.cells:
        print(f"  {c.fqn}: {c.type}   [{c.export}]")
    print("kept interpreted:")
    for s in m.skipped:
        print(f"  {s.fqn}: {s.reason}")


if __name__ == "__main__":
    main()
