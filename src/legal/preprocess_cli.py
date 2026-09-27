"""Command line interface for document conversion."""

import argparse
import sys

from .formats import Invalid, exception_result, fail, output
from .preprocessing import convert


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENT", "/arguments", message)


def main(argv=None):
    parser = Parser(prog="python -m legal.preprocess_cli")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--converter-config", required=True)
    try:
        actual = list(sys.argv[1:] if argv is None else argv)
        seen = set()
        for part in actual:
            if part.startswith("--"):
                key = part.split("=", 1)[0]
                if key in seen:
                    fail("INVALID_ARGUMENT", "/arguments/" + key[2:], "argument repeated")
                seen.add(key)
        args = parser.parse_args(actual)
        return output(convert(args.input, args.output_dir, args.converter_config))
    except Exception as exc:
        return exception_result(exc)


if __name__ == "__main__":
    raise SystemExit(main())
