import typer

from spy.libspy_build import cache_dir, clear_cache

cache_app = typer.Typer(
    help="Manage the libspy variants which are built on demand",
    no_args_is_help=True,
)


@cache_app.command("clear")
def clear() -> None:
    """Delete the libspy variants built on demand"""
    root = cache_dir()
    n = clear_cache()
    if n == 0:
        print(f"Nothing to remove in {root}")
    else:
        print(f"Removed {n} libspy build(s) from {root}")
