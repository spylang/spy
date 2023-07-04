# type: ignore

import py
ROOT = py.path.local(__file__).dirpath()

def pytest_collection_modifyitems(session, config, items):
    """
    Reorder the test to have a "better" order. In particular:

      - test_zz_mypy.py is always the last, after the subdirectories
      - compiler/*.py comes after everythig else (apart mypy)

    The reasoning is that compiler/*.py tests are integration tests and it
    makes sense to run them after the unit tests. And mypy should be last
    because we are not interested in type errors if there are failures.
    """
    def key(item):
        filename = item.fspath.relto(ROOT)
        if filename == 'test_zz_mypy.py':
            return 100 # last
        elif filename.startswith('compiler/'):
            return 99  # second to last
        else:
            return 0   # don't touch

    items.sort(key=key)
