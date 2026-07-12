"""Governance-doc conformance tests.

Per templateConformance.md §Gap 3-4 (compliance checklist):

- ``.claude/CLAUDE.md`` exists and links every ``*.md`` under ``.claude/specs/``.
- ``README.md`` no longer contains the "Boilerplate" stub text.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / ".claude" / "CLAUDE.md"
SPECS_DIR = REPO_ROOT / ".claude" / "specs"
README_MD = REPO_ROOT / "README.md"


class TestClaudeMdExistsAndLinksSpecs(unittest.TestCase):
    def test_claude_md_exists(self) -> None:
        self.assertTrue(CLAUDE_MD.is_file(), f"expected {CLAUDE_MD} to exist")

    def test_claude_md_links_every_spec(self) -> None:
        claude_md_text = CLAUDE_MD.read_text(encoding="utf-8")
        spec_files = sorted(SPECS_DIR.glob("*.md"))
        self.assertGreaterEqual(len(spec_files), 1, f"expected specs under {SPECS_DIR}")

        missing = [
            spec_file.name for spec_file in spec_files if spec_file.name not in claude_md_text
        ]
        self.assertEqual(
            missing,
            [],
            f".claude/CLAUDE.md is missing links to: {missing}",
        )


class TestReadmeHasNoBoilerplate(unittest.TestCase):
    def test_readme_exists(self) -> None:
        self.assertTrue(README_MD.is_file(), f"expected {README_MD} to exist")

    def test_readme_contains_no_boilerplate_text(self) -> None:
        readme_text = README_MD.read_text(encoding="utf-8")
        self.assertNotIn("Boilerplate", readme_text)


if __name__ == "__main__":
    unittest.main()
