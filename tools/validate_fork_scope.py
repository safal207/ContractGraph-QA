#!/usr/bin/env python3
"""Fail-closed preflight validation for authorized fork runs."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ZERO_ADDRESS = "0x" + "0" * 40


@dataclass(frozen=True)
class ForkScope:
    scope_id: str
    authorization_reference: str
    chain_id: int
    block_number: int
    target: str
    confirmed: str


def validate_scope(scope: ForkScope) -> dict[str, object]:
    if scope.confirmed != "YES":
        raise ValueError("authorization confirmation must be YES")
    if not scope.scope_id.strip():
        raise ValueError("scope id is required")
    if not scope.authorization_reference.strip():
        raise ValueError("authorization reference is required")
    if scope.chain_id <= 0:
        raise ValueError("chain id must be positive")
    if scope.block_number <= 0:
        raise ValueError("block number must be positive")
    if not ADDRESS_RE.fullmatch(scope.target):
        raise ValueError("target must be a 20-byte hex address")
    if scope.target.lower() == ZERO_ADDRESS:
        raise ValueError("target cannot be the zero address")

    result = asdict(scope)
    result["target"] = scope.target.lower()
    result.pop("confirmed")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--chain-id", required=True, type=int)
    parser.add_argument("--block-number", required=True, type=int)
    parser.add_argument("--target", required=True)
    parser.add_argument("--confirmed", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scope = ForkScope(
        scope_id=args.scope_id,
        authorization_reference=args.authorization_reference,
        chain_id=args.chain_id,
        block_number=args.block_number,
        target=args.target,
        confirmed=args.confirmed,
    )
    validated = validate_scope(scope)
    print(json.dumps(validated, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
