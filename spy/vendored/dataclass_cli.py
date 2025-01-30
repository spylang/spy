# copied and adapted from this code by @tbenthompson (Ben Thompson):
# https://github.com/fastapi/typer/issues/154#issuecomment-1544876144

import inspect
import dataclasses
import typer


def dataclass_cli(func):
    """
    Converts a function taking a dataclass as its first argument into a
    dataclass that can be called via `typer` as a CLI.

    Additionally, the --config option will load a yaml configuration before the
    other arguments.

    Modified from:
    - https://github.com/tiangolo/typer/issues/197

    A couple related issues:
    - https://github.com/tiangolo/typer/issues/153
    - https://github.com/tiangolo/typer/issues/154
    """

    # The dataclass type is the first argument of the function.
    sig = inspect.signature(func)
    param = list(sig.parameters.values())[0]
    cls = param.annotation
    assert dataclasses.is_dataclass(cls)

    def wrapped(**kwargs):
        # Load the config file if specified.
        if kwargs.get("config", "") != "":
            with open(kwargs["config"], "r") as f:
                conf = yaml.safe_load(f)
        else:
            conf = {}

        # CLI options override the config file.
        conf.update(kwargs)

        # Convert back to the original dataclass type.
        arg = cls(**conf)

        # Actually call the entry point function.
        return func(arg)

    # To construct the signature, we remove the first argument (self)
    # from the dataclass __init__ signature.
    signature = inspect.signature(cls.__init__)
    parameters = list(signature.parameters.values())
    if len(parameters) > 0 and parameters[0].name == "self":
        del parameters[0]

    # Add the --config option to the signature.
    # When called through the CLI, we need to set defaults via the YAML file.
    # Otherwise, every field will get overwritten when the YAML is loaded.
    parameters = [
        inspect.Parameter(
            "config",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=typer.Option("", callback=conf_callback, is_eager=True),
        )
    ] + [p for p in parameters if p.name != "config"]

    # The new signature is compatible with the **kwargs argument.
    wrapped.__signature__ = signature.replace(parameters=parameters)

    # The docstring is used for the explainer text in the CLI.
    wrapped.__doc__ = func.__doc__ + "\n" + ""

    return wrapped
