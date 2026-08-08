"""Self-contained product demo that runs from the installed wheel without a repository checkout."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from contractgraph_qa.product import CaptureConfig, ProductConfig, ProductError, run_pipeline

DEMO_FINDING_ID = "CGQA-005"


def _canonical_text_bytes(data: bytes) -> bytes:
    """Normalize packaged text assets so checkout line endings cannot affect evidence bytes."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _asset_bytes(name: str) -> bytes:
    return _canonical_text_bytes(
        files("contractgraph_qa").joinpath("demo_assets", name).read_bytes()
    )


def run_demo(output_dir: Path) -> dict[str, object]:
    destination = output_dir.expanduser().resolve()
    if destination.exists():
        if not destination.is_dir():
            raise ProductError(f"demo destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise ProductError(
                f"demo destination is not empty: {destination}; choose a fresh directory"
            )
    destination.mkdir(parents=True, exist_ok=True)

    inputs = destination / "inputs"
    inputs.mkdir()
    manifest = inputs / "manifest.json"
    result = inputs / "result.json"
    manifest.write_bytes(_asset_bytes("manifest.json"))
    result.write_bytes(_asset_bytes("result.json"))

    config = ProductConfig(
        source=destination / "cgqa-demo.toml",
        working_directory=destination,
        manifest=manifest,
        result=result,
        finding=destination / f"{DEMO_FINDING_ID}.finding.json",
        report=destination / f"{DEMO_FINDING_ID}.md",
        bundle=destination / f"{DEMO_FINDING_ID}.evidence.zip",
        capture=CaptureConfig(
            enabled=False,
            profile="capture",
            test="test_CaptureExplorerResult",
            verbosity=0,
        ),
    )
    summary = run_pipeline(config)
    summary["demo"] = True
    summary["outputDirectory"] = str(destination)
    summary["note"] = (
        "Repository-owned demo evidence only; this is not an external audit or authorization."
    )
    return summary
