import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.cli import main


class AstraStatePlanesCliTests(unittest.TestCase):
    def test_cli_reports_state_hash_suspicion(self):
        payload = {
            "states": [
                {
                    "id": "s1",
                    "state_hash": "same",
                    "future_signature": "can-settle",
                    "primary": {"fingerprint": "pending", "source_root": "storage"},
                    "witnesses": [
                        {
                            "id": "w1",
                            "fingerprint": "pending",
                            "source_root": "chain",
                            "independent": True,
                        }
                    ],
                },
                {
                    "id": "s2",
                    "state_hash": "same",
                    "future_signature": "cannot-settle",
                    "primary": {"fingerprint": "pending", "source_root": "storage"},
                    "witnesses": [
                        {
                            "id": "w2",
                            "fingerprint": "pending",
                            "source_root": "chain",
                            "independent": True,
                        }
                    ],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "planes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["astra-state-planes", "--input", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["schema_version"], "astra-state-planes-v0.1")
        self.assertEqual(result["verdict"], "REVIEW_REQUIRED")
        self.assertEqual(
            result["state_hash_suspicions"][0]["status"], "STATE_HASH_SUSPECT"
        )


if __name__ == "__main__":
    unittest.main()
