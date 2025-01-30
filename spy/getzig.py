"""
Small utility to get the path to the zig executable installed via:
    pip install ziglang
"""

from pathlib import Path
import ziglang

ZIG = Path(ziglang.__file__).parent.joinpath('zig')
assert ZIG.exists()

if __name__ == "__main__":
    print(ZIG)
