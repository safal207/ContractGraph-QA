# Contributing

ContractGraph-QA is a smart-contract QA and audit-readiness project. Contributions should preserve deterministic evidence, explicit authorization boundaries, and reproducible tests.

## Development setup

Requirements:

- Python 3.11+;
- Foundry 1.7.x-compatible toolchain;
- Slither for the advisory static-analysis job.

Install the product runtime from a checkout:

```bash
python -m pip install -e .
```

Run the local gates:

```bash
forge fmt --check
forge build --sizes
forge test -vvv
python -m unittest discover -s tools/tests -p 'test_*.py' -v
cgqa run --config cgqa.example.toml --clean
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

## Change expectations

### Solidity explorer changes

Add or update tests that prove:

- minimal-path behavior;
- deterministic replay;
- invariant behavior;
- state-hash completeness assumptions;
- bounded resource behavior.

### Manifest/result/report changes

Preserve strict validation. Do not silently accept unknown fields or provenance mismatches.

When a deterministic format changes intentionally, update both the machine-readable fixture and its golden output in the same pull request.

### Product runtime changes

Preserve:

- no-shell capture invocation;
- stable exit-code semantics;
- deterministic bundle construction;
- independent bundle verification;
- backward compatibility for the current bundle version unless explicitly versioned.

## Safety

Do not add examples or tests that require unauthorized interaction with a third-party production contract.

Use repository-owned local fixtures or explicitly authorized scopes. Never commit RPC secrets, private keys, seed phrases, or client secrets.

## Pull requests

A product-facing pull request should include:

- what changed;
- why it changed;
- user/operator impact;
- safety or provenance impact;
- exact validation performed;
- known limitations.
