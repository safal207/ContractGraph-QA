from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TX_HASH = "0xf38fb9962dbee2fc35bd156140bd623d3ce74b92efdcf6a50c5869126c0b6273"
CHAIN_URL = "https://api.arc-scan.org/v1/chain"
RAW_URL = f"https://api.arc-scan.org/v1/txs/{TX_HASH}/raw"
EXPECTED_CHAIN_ID = 5042
EXPECTED_USDC = "0x3600000000000000000000000000000000000000"
MIRROR = "0xfffffffffffffffffffffffffffffffffffffffe"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ContractGraph-QA Astra receipt acquisition/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read()


def walk_strings(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value


def collect_log_addresses(value: Any) -> list[str]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            address = node.get("address")
            topics = node.get("topics")
            if isinstance(address, str) and isinstance(topics, list):
                found.append(address.lower())
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    chain_raw = fetch(CHAIN_URL)
    receipt_raw = fetch(RAW_URL)

    chain = json.loads(chain_raw)
    receipt = json.loads(receipt_raw)

    chain_id = chain.get("chain_id")
    if chain_id != EXPECTED_CHAIN_ID:
        raise RuntimeError(
            f"wrong Arc chain id: expected {EXPECTED_CHAIN_ID}, got {chain_id!r}"
        )

    flattened = "\n".join(walk_strings(receipt)).lower()
    if TX_HASH.lower() not in flattened:
        raise RuntimeError("raw transaction response does not contain the pinned tx hash")

    log_addresses = collect_log_addresses(receipt)
    if not log_addresses:
        raise RuntimeError("raw transaction response contains no receipt-like logs")

    chain_path = args.out_dir / "chain.raw.json"
    receipt_path = args.out_dir / "transaction.raw.json"
    chain_canonical_path = args.out_dir / "chain.canonical.json"
    receipt_canonical_path = args.out_dir / "transaction.canonical.json"

    chain_path.write_bytes(chain_raw)
    receipt_path.write_bytes(receipt_raw)
    chain_canonical_path.write_bytes(canonical_json_bytes(chain))
    receipt_canonical_path.write_bytes(canonical_json_bytes(receipt))

    manifest = {
        "schema": "contractgraph.astra-arc-receipt-acquisition.v0.1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "chain_url": CHAIN_URL,
            "raw_transaction_url": RAW_URL,
        },
        "subject": {
            "network": "eip155:5042",
            "chain_id": EXPECTED_CHAIN_ID,
            "tx_hash": TX_HASH,
            "expected_payment_asset": EXPECTED_USDC,
            "known_mirror_contract": MIRROR,
        },
        "artifacts": {
            "chain_raw": {
                "path": chain_path.name,
                "bytes": len(chain_raw),
                "sha256": sha256(chain_raw),
            },
            "transaction_raw": {
                "path": receipt_path.name,
                "bytes": len(receipt_raw),
                "sha256": sha256(receipt_raw),
            },
            "chain_canonical": {
                "path": chain_canonical_path.name,
                "bytes": chain_canonical_path.stat().st_size,
                "sha256": sha256(chain_canonical_path.read_bytes()),
            },
            "transaction_canonical": {
                "path": receipt_canonical_path.name,
                "bytes": receipt_canonical_path.stat().st_size,
                "sha256": sha256(receipt_canonical_path.read_bytes()),
            },
        },
        "observed": {
            "log_count": len(log_addresses),
            "log_addresses_in_order": log_addresses,
            "expected_payment_asset_log_present": EXPECTED_USDC in log_addresses,
            "mirror_log_present": MIRROR in log_addresses,
        },
        "claim_boundary": (
            "This is a read-only acquisition artifact. It does not establish payment "
            "binding, amount correctness, delivery, or a PASS/FAIL verdict."
        ),
    }

    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
