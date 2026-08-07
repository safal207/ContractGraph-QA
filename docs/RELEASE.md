# Release process

ContractGraph-QA product releases use Semantic Versioning.

## Release gate

A release candidate must satisfy the v1.0 Definition of Done in `docs/PRODUCT.md` on the exact release head.

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
cgqa run --config cgqa.example.toml --clean
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

The normal CI, reporting CI, product E2E job, and Slither advisory scan must all be green.

## Version synchronization

Before tagging, the same version must appear in:

- `pyproject.toml` under `[project].version`;
- `contractgraph_qa/__init__.py` as `__version__`;
- the top release entry in `CHANGELOG.md`.

## Build artifact

Build a wheel from a clean checkout:

```bash
rm -rf build dist *.egg-info .product-wheel
python -m pip wheel . --no-deps --wheel-dir .product-wheel
```

Install that wheel into a clean Python environment and run the product smoke commands above.

## Tagging

After the release head is reviewed and merged:

```text
vMAJOR.MINOR.PATCH
```

Example:

```text
v1.0.0
```

Do not tag a commit that differs from the exact head used for the final green product gate.

## Release notes

Release notes should state:

- product/runtime changes;
- engine changes;
- evidence-format changes;
- safety/authorization boundary changes;
- compatibility notes;
- known limitations.

## Evidence compatibility

`bundleVersion` controls evidence ZIP compatibility independently from the package version.

A product patch/minor release may keep `bundleVersion = 1` as long as it can still verify the same five-file semantic contract without ambiguity.

A breaking bundle layout or meaning change requires a new bundle version and explicit compatibility handling in `cgqa verify-bundle`.
