#-*- encoding: utf-8 -*-
import typing

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
