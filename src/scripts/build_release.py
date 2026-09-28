"""Build the installable wheel without including contract data."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable, help="Build interpreter with pip, setuptools and wheel")
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [args.python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(output), str(SOURCE)],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
