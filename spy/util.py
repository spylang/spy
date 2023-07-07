#-*- encoding: utf-8 -*-
import typing
from typing import Optional

class AnythingClass:
    """
    Magic object which compares equal to everything. Useful for equality tests
    in which you don't care about the exact value of a specific field.
    """
    def __eq__(self, other: typing.Any) -> bool:
        return True

ANYTHING: typing.Any = AnythingClass()


@typing.no_type_check
def magic_dispatch(self, prefix, obj, *args, **kwargs):
    """
    Dynamically dispatch the execution to a method whose name is computed from
    `prefix` and the class name of `obj`.

    Example:

    class Foo:
        def visit(self, obj):
            return magic_dispatch(self, 'visit', obj)

        def visit_int(self): ...
        def visit_str(self): ...
        def visit_float(self): ...
    """
    methname = f'{prefix}_{obj.__class__.__name__}'
    meth = getattr(self, methname, None)
    if meth is None:
        meth = getattr(self, f'{prefix}_NotImplemented', None)
        if meth is None:
            clsname = self.__class__.__name__
            raise NotImplementedError(f'{clsname}.{methname}')
    return meth(obj, *args, **kwargs)


@typing.no_type_check
def extend(existing_cls):
    """
    Class decorator to extend an existing class with new attributes and
    methods
    """
    def decorator(new_cls):
        for key, value in new_cls.__dict__.items():
            if key.startswith('__'):
                continue
            if hasattr(existing_cls, key):
                clsname = existing_cls.__name__
                raise TypeError(f"class {clsname} has already a member '{key}'")
            setattr(existing_cls, key, value)
        return existing_cls
    return decorator


@typing.no_type_check
def print_class_hierarchy(cls):
    CROSS  = "├── "
    BAR    = "│   "
    CORNER = "└── "
    SPACE  = "    "

    def print_class(cls, prefix, indent, marker):
        print(f'{prefix}{marker}{cls.__name__}')
        prefix += indent
        subclasses = cls.__subclasses__()
        if subclasses:
            for subcls in subclasses[:-1]:
                print_class(subcls, prefix, indent=BAR, marker=CROSS)
            print_class(subclasses[-1], prefix, indent=SPACE, marker=CORNER)

    print_class(cls, prefix='', indent='', marker='')


class ColorFormatter:
    black = '30'
    darkred = '31'
    darkgreen = '32'
    brown = '33'
    darkblue = '34'
    purple = '35'
    teal = '36'
    lightgray = '37'
    darkgray = '30;01'
    red = '31;01'
    green = '32;01'
    yellow = '33;01'
    blue = '34;01'
    fuchsia = '35;01'
    turquoise = '36;01'
    white = '37;01'

    def __init__(self, use_colors: bool) -> None:
        self._use_colors = use_colors

    def set(self, color: Optional[str], s: str) -> str:
        if color is None or not self._use_colors:
            return s
        try:
            color = getattr(self, color)
        except AttributeError:
            pass
        return '\x1b[%sm%s\x1b[00m' % (color, s)

# create a global instance, so that you can just do Color.set('red', ....)
Color = ColorFormatter(use_colors=True)

if __name__ == '__main__':
    import ast as py_ast
    print_class_hierarchy(py_ast.AST)
