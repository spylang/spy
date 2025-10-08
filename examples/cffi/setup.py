from setuptools import setup

# this assumes that you already invoked 'spy' to generate the bindings, see
# README

setup(
    name="spydemo",
    setup_requires=["cffi"],
    install_requires=["cffi"],

    package_dir={"": "build/cffi"},
    py_modules=["spydemo"],
    cffi_modules=["./build/cffi/_spydemo-cffi-build.py:ffibuilder"],
)
