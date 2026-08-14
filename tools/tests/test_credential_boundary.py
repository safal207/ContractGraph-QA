from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.credential_boundary import scan_repository


class CredentialBoundaryTest(unittest.TestCase):
    def _repo(self) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="cgqa-boundary-"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=directory, check=True)
        return directory

    def _track(self, directory: Path, *paths: str) -> None:
        subprocess.run(["git", "add", *paths], cwd=directory, check=True)

    def test_runtime_env_file_is_blocked(self) -> None:
        directory = self._repo()
        (directory / ".env").write_text("OPENAI_API_KEY=provided\n", encoding="utf-8")
        self._track(directory, ".env")

        result = scan_repository(directory)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["violations"][0]["rule"], "tracked-runtime-environment-file")

    def test_example_and_environment_reference_are_allowed(self) -> None:
        directory = self._repo()
        (directory / ".env.example").write_text("OPENAI_API_KEY=<set via secret store>\n", encoding="utf-8")
        (directory / "config.yml").write_text("OPENAI_API_KEY: ${OPENAI_API_KEY}\n", encoding="utf-8")
        self._track(directory, ".env.example", "config.yml")

        result = scan_repository(directory)

        self.assertEqual(result["decision"], "PASS")

    def test_explicit_fixture_marker_is_narrow_and_token_safe(self) -> None:
        directory = self._repo()
        fake_token = "sk-" + "123456789012345678901234"
        (directory / "fixture.yml").write_text(
            "POSTGRES_PASSWORD: ci-only # fcrp: fixture\n"
            f"fixture_token: {fake_token} # fcrp: fixture\n",
            encoding="utf-8",
        )
        self._track(directory, "fixture.yml")

        result = scan_repository(directory)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["violations"][0]["rule"], "openai-token-shape")
        self.assertEqual(len(result["violations"]), 1)

    def test_provider_token_shape_is_blocked_without_printing_value(self) -> None:
        directory = self._repo()
        fake_token = "sk-" + "123456789012345678901234"
        (directory / "config.txt").write_text(f"token={fake_token}\n", encoding="utf-8")
        self._track(directory, "config.txt")

        result = scan_repository(directory)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["violations"][0]["rule"], "openai-token-shape")


if __name__ == "__main__":
    unittest.main()
