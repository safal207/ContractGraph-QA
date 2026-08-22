from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main
from contractgraph_qa.runtime_conformance_profile import (
    PROFILE_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    evaluate_runtime_conformance_profile,
    load_runtime_conformance_profile,
    validate_runtime_conformance_profile,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "openai-agents-runtime-conformance-profile-v0.1.json"
SCHEMA = ROOT / "contractgraph_qa" / "schemas" / "agent-runtime-conformance-profile-v0.1.schema.json"


class RuntimeConformanceProfileTest(unittest.TestCase):
    def _profile(self) -> dict[str, object]:
        with EXAMPLE.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_canonical_profile_is_valid_and_machine_readable(self) -> None:
        profile = load_runtime_conformance_profile(EXAMPLE)
        result = evaluate_runtime_conformance_profile(profile)

        self.assertEqual(profile["schemaVersion"], PROFILE_SCHEMA_VERSION)
        self.assertEqual(result["schemaVersion"], VALIDATION_SCHEMA_VERSION)
        self.assertTrue(result["profileValid"])
        self.assertTrue(result["projectionConformant"])
        self.assertEqual(result["projection"], {"status": "pass", "passed": 8, "total": 8})
        self.assertEqual(result["axes"]["appendOnly"], "fail")
        self.assertEqual(result["axes"]["destructiveMutations"], "present")
        self.assertEqual(result["destructiveMutationOperations"], ["pop_item", "clear_session"])

    def test_projection_score_and_status_must_agree(self) -> None:
        profile = self._profile()
        profile["projection"]["passed"] = 7
        with self.assertRaisesRegex(ValueError, "projection status and score disagree"):
            validate_runtime_conformance_profile(profile)

    def test_projection_pass_requires_embedded_projection_axes_to_pass(self) -> None:
        profile = self._profile()
        profile["deadlineBinding"] = "fail"
        with self.assertRaisesRegex(ValueError, "projection=pass requires deadlineBinding=pass"):
            validate_runtime_conformance_profile(profile)

    def test_destructive_mutations_force_append_only_fail(self) -> None:
        profile = self._profile()
        profile["appendOnly"] = "pass"
        with self.assertRaisesRegex(ValueError, "observed destructive mutations require appendOnly=fail"):
            validate_runtime_conformance_profile(profile)

    def test_evidence_refs_are_required(self) -> None:
        profile = self._profile()
        profile["evidenceRefs"] = []
        with self.assertRaisesRegex(ValueError, "evidenceRefs must be a non-empty string array"):
            validate_runtime_conformance_profile(profile)

    def test_schema_file_is_valid_json_and_matches_profile_version(self) -> None:
        with SCHEMA.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], PROFILE_SCHEMA_VERSION)
        self.assertFalse(schema["additionalProperties"])

    def test_cli_separates_profile_validity_from_projection_conformance(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["runtime-conformance-profile", "--input", str(EXAMPLE)])
        result = json.loads(stdout.getvalue())

        self.assertEqual(code, EXIT_OK)
        self.assertTrue(result["profileValid"])
        self.assertTrue(result["projectionConformant"])
        self.assertEqual(result["axes"]["appendOnly"], "fail")

    def test_cli_invalid_profile_returns_validation_exit(self) -> None:
        profile = copy.deepcopy(self._profile())
        profile["source"]["commit"] = "main"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["runtime-conformance-profile", "--input", str(path)])

        self.assertEqual(code, EXIT_VALIDATION)
        self.assertIn("pinned 40-character lowercase SHA", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
