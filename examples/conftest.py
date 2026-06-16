# type: ignore


def pytest_addoption(parser):
    parser.addoption(
        "--update-expected-output",
        action="store_true",
        default=False,
        help="Overwrite expected output files instead of comparing against them.",
    )
