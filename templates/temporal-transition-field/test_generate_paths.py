import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("generator", HERE / "generate_paths.py")
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generator)


class GeneratePathsTests(unittest.TestCase):
    def test_parse_transitions_supports_inline_and_block_yaml(self):
        text = """
transitions:
  - {from: \"Q0\", event: \"start\", to: \"Q1\"}
  - from: Q1
    event: finish
    to: Q2
"""
        self.assertEqual(
            generator.parse_transitions(text),
            [("Q0", "start", "Q1"), ("Q1", "finish", "Q2")],
        )

    def test_parse_transitions_rejects_incomplete_entry(self):
        text = """
transitions:
  - from: Q0
    event: start
"""
        with self.assertRaisesRegex(ValueError, r"transitions\[0\]\.to"):
            generator.parse_transitions(text)

    def test_generate_paths_stops_at_max_paths(self):
        text = """
transitions:
  - {from: Q0_RESET, event: a, to: Q1}
  - {from: Q0_RESET, event: b, to: Q2}
  - {from: Q0_RESET, event: c, to: Q3}
  - {from: Q1, event: d, to: Q4}
  - {from: Q2, event: e, to: Q5}
  - {from: Q3, event: f, to: Q6}
"""
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "field.yaml"
            spec_path.write_text(text, encoding="utf-8")
            with mock.patch.object(generator, "SPEC", spec_path):
                paths = generator.generate_paths(max_depth=6, max_paths=2)
        self.assertEqual(len(paths), 2)
        self.assertEqual([path[0][1] for path in paths], ["a", "b"])

    def test_invalid_bounds_fail_fast(self):
        with self.assertRaises(ValueError):
            generator.generate_paths(max_depth=0)
        with self.assertRaises(ValueError):
            generator.generate_paths(max_paths=0)


if __name__ == "__main__":
    unittest.main()
