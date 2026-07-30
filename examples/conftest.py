# type: ignore


def pytest_addoption(parser):
    parser.addoption(
        "--update-examples",
        action="store_true",
        default=False,
        help="Overwrite expected output files instead of comparing against them.",
    )
