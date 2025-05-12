from setuptools import setup

setup(
    name="spydemo",
    setup_requires=['cffi'],
    install_requires=['cffi'],

    package_dir={'': 'build/cffi'},
    py_modules=['spydemo'],
    cffi_modules=["./build/cffi/_spydemo-cffi-build.py:ffibuilder"],
)
