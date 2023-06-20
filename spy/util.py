#-*- encoding: utf-8 -*-
import typing

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
        raise NotImplementedError(methname)
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

if __name__ == '__main__':
    import ast as py_ast
    print_class_hierarchy(py_ast.AST)
