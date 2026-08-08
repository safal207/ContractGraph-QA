# Release process

ContractGraph-QA product releases use Semantic Versioning.

## Release gate

A release candidate must satisfy the current Product Definition of Done on the exact release head.

Minimum checks:

```bash
forge fmt --check
forge build --sizes
forge test -vvv
python -m unittest discover -s tools/tests -p 'test_*.py' -v
python -m pip wheel . --no-deps --wheel-dir .product-wheel
python -m pip install --force-reinstall .product-wheel/contractgraph_qa-*.whl
cgqa --version
cgqa doctor --require-forge
cgqa demo --output-dir /tmp/cgqa-demo
cgqa verify-bundle /tmp/cgqa-demo/CGQA-005.evidence.zip
cgqa run --config cgqa.example.toml --clean
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

The normal CI, reporting CI, product E2E job, and Slither advisory scan must all be green.

## Version synchronization

Before tagging, the same version must appear in:

- `pyproject.toml` under `[project].version`;
- `contractgraph_qa/__init__.py` as `__version__`;
- the top release entry in `CHANGELOG.md`.

`tools/check_version.py` enforces this contract and additionally checks a supplied `v<version>` tag.

## Build artifact

Build a wheel from a clean checkout:

```bash
rm -rf build dist *.egg-info .product-wheel
python -m pip wheel . --no-deps --wheel-dir .product-wheel
```

Install that wheel into a clean Python environment and run the product smoke commands above.

## Distribution workflow

v1.6 adds `.github/workflows/distribution.yml`.

On a `v*` tag (or manual workflow dispatch) it:

1. checks version/tag consistency;
2. builds the wheel;
3. installs the built wheel;
4. runs the self-serve demo outside the repository checkout;
5. verifies the demo evidence bundle;
6. assembles wheel + demo report + demo evidence + client proof;
7. creates `SHA256SUMS`;
8. uploads the verified distribution directory as a GitHub Actions artifact.

See `docs/DISTRIBUTION.md` for consumer instructions.

## Tagging

After the release head is reviewed and merged:

```text
vMAJOR.MINOR.PATCH
```

Example:

```text
v1.6.0
```

Do not tag a commit that differs from the exact head used for the final green product gate.

The repository does not currently create tags automatically; tag creation remains an explicit operator action.

## Release notes

Release notes should state:

- product/runtime changes;
- engine changes;
- evidence-format changes;
- safety/authorization boundary changes;
- compatibility notes;
- known limitations;
- distribution artifact checksum instructions.

## Evidence compatibility

`bundleVersion` controls evidence ZIP compatibility independently from the package version.

A product patch/minor release may keep the existing bundle version as long as it can still verify the same semantic contract without ambiguity.

A breaking bundle layout or meaning change requires a new bundle version and explicit compatibility handling in the relevant `cgqa verify-*` command.
