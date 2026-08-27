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
cgqa engagement-run --config cgqa.engagement.example.toml
cgqa verify-engagement-bundle dist/CGQA-E-001-run/CGQA-E-001.engagement.zip
```

The normal CI, reporting CI, Product E2E, Measurement Provenance gate, Slither advisory scan, and both Linux/Windows Portability jobs must all be green.

For v1.8+ the engagement smoke must verify the provenance-bound client ZIP and report a passing measurement-provenance boundary.

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

## Portability gate

`.github/workflows/portability.yml` builds and installs the wheel independently on Linux and Windows. It runs the demo outside the checkout twice, verifies both evidence bundles, rejects CRLF text artifacts, and requires byte-identical deterministic outputs.

This gate is part of the release contract, not an advisory check.

## Distribution workflow

`.github/workflows/distribution.yml` runs on a `v*` tag or manual dispatch.

It:

1. checks version/tag consistency;
2. builds and installs the wheel;
3. runs the self-serve demo outside the repository checkout;
4. verifies the demo evidence bundle;
5. assembles wheel + demo report + demo evidence + client proof + verification guide;
6. creates deterministic CycloneDX 1.5 `SBOM.cdx.json` bound to the wheel and source commit;
7. independently verifies the SBOM against wheel metadata and SHA-256;
8. creates and verifies `SHA256SUMS`;
9. creates GitHub/Sigstore attestation for the checksum manifest;
10. creates an SBOM attestation bound to the wheel;
11. preserves both attestation bundles in the distribution payload;
12. uploads the verified Actions artifact;
13. for a new tag, publishes the same payload as a GitHub Release.

The release step refuses to overwrite an existing GitHub Release for the same tag.

See `docs/DISTRIBUTION.md` for consumer verification instructions.

## Tagging

After the release head is reviewed and merged:

```text
vMAJOR.MINOR.PATCH
```

Current release example:

```text
v1.8.0
```

Do not tag a commit that differs from the exact head used for the final green product, measurement-provenance, and portability gates.

Tag creation remains an explicit operator action. The tag-triggered Distribution workflow owns artifact signing and GitHub Release publication.

## Release notes

Release notes should state:

- product/runtime changes;
- engine changes;
- evidence-format changes;
- measurement-provenance and coverage semantics;
- safety/authorization boundary changes;
- compatibility notes;
- known limitations;
- checksum and attestation verification instructions.

`docs/GITHUB_RELEASE.md` is the client-facing quick-start/verification body used for tag releases.

## Evidence compatibility

`bundleVersion` controls evidence ZIP compatibility independently from the package version.

A product patch/minor release may keep an existing embedded bundle version as long as it can still verify the same semantic contract without ambiguity.

The v1.8 engagement provenance wrapper intentionally contains and independently verifies the legacy engagement bundle rather than silently redefining it. `cgqa verify-engagement-bundle` auto-detects both layouts.

A breaking bundle layout or meaning change requires a new bundle version and explicit compatibility handling in the relevant `cgqa verify-*` command.

Supply-chain attestations do not replace evidence-bundle semantic verification; they add release provenance around the distributed product artifacts.
