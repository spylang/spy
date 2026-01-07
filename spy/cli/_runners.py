import pdb as stdlib_pdb  # to distinguish from the "--pdb" option  # to distinguish from the "--pdb" option
import sys
import time
import traceback
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import (
    Callable,
    Generator,
    Optional,
    Protocol,
)

from spy.cli.commands.shared_args import Base_Args
from spy.doppler import ErrorMode
from spy.errors import SPyError
from spy.textbuilder import Color
from spy.vm.b import B
from spy.vm.debugger.spdb import SPdb
from spy.vm.function import W_ASTFunc, W_FuncType
from spy.vm.module import W_Module
from spy.vm.vm import SPyVM

GLOBAL_VM: Optional[SPyVM] = None


async def _pyodide_main(user_func: Callable, args: "Base_Args") -> None:
    """
    For some reasons, it seems that pyodide doesn't print exceptions
    uncaught exceptions which escapes an asyncio task. This is a small wrapper
    to ensure that we display a proper traceback in that case
    """
    try:
        await _run_command(user_func, args)
    except BaseException:
        traceback.print_exc()


async def _run_command(user_func: Callable, args: "Base_Args") -> None:
    """
    A wrapper around the user provided command,
    to catch/display SPy errors and to implement --pdb
    """
    try:
        return await user_func(args)
    except SPyError as e:
        ## traceback.print_exc()
        ## print()

        # special case SPdbQuit
        if e.etype == "W_SPdbQuit":
            print("SPdbQuit")
            sys.exit(1)

        print(e.format(use_colors=True))

        if args.spdb:
            # post-mortem applevel debugger
            assert GLOBAL_VM is not None
            w_tb = e.w_exc.w_tb
            assert w_tb is not None
            spdb = SPdb(GLOBAL_VM, w_tb)
            spdb.post_mortem()
        elif args.pdb:
            # post-mortem interp-level debugger
            info = sys.exc_info()
            stdlib_pdb.post_mortem(info[2])
        sys.exit(1)
    except Exception as e:
        if not args.pdb:
            raise
        traceback.print_exc()
        info = sys.exc_info()
        stdlib_pdb.post_mortem(info[2])
        sys.exit(1)


def execute_spy_main(
    vm: SPyVM, w_mod: W_Module, redshift: bool = False, _timeit: bool = False
) -> None:
    w_main_functype = W_FuncType.parse("def() -> None")
    w_main = w_mod.getattr_maybe("main")
    if w_main is None:
        print("Cannot find function main()")
        return

    vm.typecheck(w_main, w_main_functype)
    assert isinstance(w_main, W_ASTFunc)

    # find the redshifted version, if necessary
    if redshift:
        assert not w_main.is_valid
        assert w_main.w_redshifted_into is not None
        w_main = w_main.w_redshifted_into
        assert w_main.redshifted
    else:
        assert not w_main.redshifted

    with timer() if _timeit else nullcontext():
        w_res = vm.fast_call(w_main, [])
    assert w_res is B.w_None


class Init_Args(Protocol):
    error_mode: ErrorMode
    filename: Path


async def init_vm(args: Init_Args) -> SPyVM:
    global GLOBAL_VM

    if args.filename.suffix == ".py":
        print(
            f"Error: {args.filename} is a .py file, not a .spy file.", file=sys.stderr
        )
        sys.exit(1)

    srcdir = args.filename.parent
    vm = await SPyVM.async_new()

    GLOBAL_VM = vm

    vm.robust_import_caching = True  # don't raise if .spyc are unreadable/invalid

    vm.path.append(str(srcdir))
    if args.error_mode == "warn":
        args.error_mode = "lazy"

        def emit_warning(err: SPyError) -> None:
            print(Color.set("yellow", "[warning] "), end="")
            print(err.format())

        vm.emit_warning = emit_warning
    return vm


@contextmanager
def timer() -> Generator:
    a = time.time()
    yield
    b = time.time()
    print(f"main(): {b - a:.3f} seconds", file=sys.stderr)
