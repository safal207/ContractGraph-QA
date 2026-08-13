from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.postimpact import (  # noqa: E402
    CONTAINMENT_KEYS,
    CONTAINMENT_OUTCOMES,
    POST_IMPACT_MODEL_KEYS,
    RECOVERY_KEYS,
    RECOVERY_OUTCOMES,
    RECOVERY_REQUIRED_KEYS,
    VERIFICATION_KEYS,
    VERIFICATION_OUTCOMES,
    VERIFICATION_SUBJECT_TYPES,
    load_post_impact_model,
    post_impact_model_from_dict,
    post_impact_model_sha256,
    run_post_impact_model,
)
from contractgraph_qa.reachability import (  # noqa: E402
    load_reachability_model,
    run_reachability_model,
)


class PostImpactGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reachability_path = ROOT / "scenarios" / "adversarial-adapter-fixture.json"
        cls.post_impact_path = ROOT / "scenarios" / "post-impact-adapter-fixture.json"

    def test_repository_fixture_binds_containment_recovery_and_verification(self) -> None:
        reachability_model = load_reachability_model(self.reachability_path)
        reachability_result = run_reachability_model(reachability_model)
        post_impact_model = load_post_impact_model(self.post_impact_path)

        first = run_post_impact_model(post_impact_model, reachability_model, reachability_result)
        second = run_post_impact_model(post_impact_model, reachability_model, reachability_result)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "contained_and_verified")
        self.assertEqual(first["boundTargetCapability"], "terminal-state-reachable")
        self.assertEqual(first["postImpactModelSha256"], post_impact_model_sha256(post_impact_model))
        self.assertEqual(first["boundReachabilityModelSha256"], reachability_result["modelSha256"])

        graph = first["controlGraph"]
        self.assertIsInstance(graph, dict)
        assert isinstance(graph, dict)
        relations = {edge["relation"] for edge in graph["edges"]}
        self.assertEqual(relations, {"contained_by", "recovered_by", "restores_to", "verified_by"})
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertIn("capability:terminal-state-reachable", node_ids)
        self.assertIn("containment:terminal-state-containment", node_ids)
        self.assertIn("recovery:reset-fixture-state", node_ids)
        self.assertIn("verification:verify-recovery", node_ids)
        self.assertIn("capability:advance-state-machine", node_ids)

    def test_unrelated_containment_cannot_bind_to_selected_forbidden_capability(self) -> None:
        reachability_model = load_reachability_model(self.reachability_path)
        reachability_result = run_reachability_model(reachability_model)
        data = json.loads(self.post_impact_path.read_text(encoding="utf-8"))
        data["containments"][0]["capabilityId"] = "advance-state-machine"
        model = post_impact_model_from_dict(data)

        with self.assertRaisesRegex(ValueError, "no containment for target capability"):
            run_post_impact_model(model, reachability_model, reachability_result)

    def test_recovery_cannot_restore_to_forbidden_capability(self) -> None:
        reachability_model = load_reachability_model(self.reachability_path)
        reachability_result = run_reachability_model(reachability_model)
        data = json.loads(self.post_impact_path.read_text(encoding="utf-8"))
        data["recoveries"][0]["restoredCapabilityId"] = "terminal-state-reachable"
        model = post_impact_model_from_dict(data)

        with self.assertRaisesRegex(ValueError, "recovered capability must not be forbidden"):
            run_post_impact_model(model, reachability_model, reachability_result)

    def test_loader_rejects_dangling_verification_and_bad_recovery_shape(self) -> None:
        data = json.loads(self.post_impact_path.read_text(encoding="utf-8"))

        dangling = copy.deepcopy(data)
        dangling["verifications"][0]["subjectId"] = "missing-control"
        with self.assertRaisesRegex(ValueError, "verification references unknown containment"):
            post_impact_model_from_dict(dangling)

        failed_with_restore = copy.deepcopy(data)
        failed_with_restore["recoveries"][0]["outcome"] = "failed"
        with self.assertRaisesRegex(ValueError, "only valid when outcome is recovered"):
            post_impact_model_from_dict(failed_with_restore)

    def test_post_impact_schema_matches_runtime_contract(self) -> None:
        schema_path = ROOT / "graph" / "schema" / "post-impact.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(set(schema["properties"]), POST_IMPACT_MODEL_KEYS)
        self.assertEqual(set(schema["required"]), POST_IMPACT_MODEL_KEYS)
        self.assertFalse(schema["additionalProperties"])

        containment = schema["$defs"]["containment"]
        self.assertEqual(set(containment["properties"]), CONTAINMENT_KEYS)
        self.assertEqual(set(containment["required"]), CONTAINMENT_KEYS)
        self.assertEqual(set(containment["properties"]["outcome"]["enum"]), CONTAINMENT_OUTCOMES)

        recovery = schema["$defs"]["recovery"]
        self.assertEqual(set(recovery["properties"]), RECOVERY_KEYS)
        self.assertEqual(set(recovery["required"]), RECOVERY_REQUIRED_KEYS)
        self.assertEqual(set(recovery["properties"]["outcome"]["enum"]), RECOVERY_OUTCOMES)

        verification = schema["$defs"]["verification"]
        self.assertEqual(set(verification["properties"]), VERIFICATION_KEYS)
        self.assertEqual(set(verification["required"]), VERIFICATION_KEYS)
        self.assertEqual(
            set(verification["properties"]["subjectType"]["enum"]),
            VERIFICATION_SUBJECT_TYPES,
        )
        self.assertEqual(
            set(verification["properties"]["outcome"]["enum"]),
            VERIFICATION_OUTCOMES,
        )


if __name__ == "__main__":
    unittest.main()
