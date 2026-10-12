#!/usr/bin/env python3
"""Independent guarded ASCII/safe-integer oracle, not a general JCS library.

This domain makes stdlib JSON output equivalent to RFC 8785 serialization:
ASCII member ordering agrees with UTF-16, strings have JSON escaping, integers
are within ±(2**53-1), and fractional/nonfinite numbers are prohibited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

FIELDS = ("spec", "issuer", "epoch", "prevRoot", "publishedAt", "governanceKeys", "keys")
SAFE_INTEGER = 2**53 - 1


def reject_float(_):
    raise ValueError("fractional/noninteger tokens are outside fixture domain")


def parse_integer(token):
    if token == "-0":
        raise ValueError("negative zero is outside fixture domain")
    return int(token)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member: " + key)
        result[key] = value
    return result


def guard(value):
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        if not value.isascii():
            raise ValueError("fixture domain requires ASCII strings and member names")
    elif type(value) is int:
        if abs(value) > SAFE_INTEGER:
            raise ValueError("integer outside ECMAScript safe-integer range")
    elif type(value) is list:
        for item in value:
            guard(item)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("member names must be strings")
            guard(key)
            guard(item)
    else:
        raise ValueError("value outside fixture canonicalization domain")


def canonicalize(value):
    guard(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def preimage(directory):
    projection = {field: directory[field] for field in FIELDS}
    projection["governanceKeys"] = sorted(directory["governanceKeys"], key=lambda key: key["alg"])
    projection["keys"] = sorted(directory["keys"], key=lambda key: key["kid"])
    return canonicalize(projection)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", type=Path, default=Path(__file__).parent / "fixtures/directory.json")
    parser.add_argument("--preimage", action="store_true", help="emit exact preimage bytes, with no newline")
    args = parser.parse_args()
    directory = json.loads(args.fixture.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
                           parse_int=parse_integer, parse_float=reject_float, parse_constant=reject_float)
    data = preimage(directory)
    root = hashlib.sha256(data).hexdigest()
    if args.preimage:
        sys.stdout.buffer.write(data)
    else:
        print(json.dumps({"scope": "ASCII/safe-integer fixture commitment only", "bytes": len(data),
                          "recomputedRoot": root, "publishedRoot": directory["root"],
                          "equal": root == directory["root"]}, sort_keys=True))
        if root != directory["root"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
