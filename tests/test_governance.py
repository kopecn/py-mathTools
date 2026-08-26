"""Governance-doc conformance tests.

Per templateConformance.md §Gap 3-4 (compliance checklist):

- ``.claude/CLAUDE.md`` exists and links every ``*.md`` under ``.claude/specs/``.
- ``README.md`` no longer contains the "Boilerplate" stub text.
- No ``pyMathTools`` (pre-rename name) references remain anywhere in the tree.
- Every public package (an ``__init__.py`` that defines ``__all__``) ships
  ``py.typed``.
"""

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / ".claude" / "CLAUDE.md"
SPECS_DIR = REPO_ROOT / ".claude" / "specs"
README_MD = REPO_ROOT / "README.md"
SRC_DIR = REPO_ROOT / "src"
MAKEFILE = REPO_ROOT / "Makefile"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"
EXAMPLES_DIR = REPO_ROOT / "examples"
TESTS_DIR = REPO_ROOT / "tests"


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


class TestNoPreRenamePackageName(unittest.TestCase):
    """templateConformance.md Gap 1 (rename): ``pyMathTools`` must never
    reappear -- a rename regression (stray import, stale doc reference)
    would otherwise pass the gate silently."""

    # Built via concatenation, not a literal, so this test doesn't trip on
    # its own docstring/name when scanning source text for the string.
    _STALE_NAME = "py" + "MathTools"

    _SCAN_ROOTS = (SRC_DIR, TESTS_DIR, EXAMPLES_DIR)
    _SCAN_FILES = (MAKEFILE, PYPROJECT_TOML)
    _TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".cfg", ".txt"}
    # This governance test's own module necessarily documents the stale
    # name it is checking for; exclude it from the scan.
    _SELF = Path(__file__).resolve()

    def test_no_pymathtools_references(self) -> None:
        hits: list[str] = []
        for root in self._SCAN_ROOTS:
            for path in root.rglob("*"):
                if (
                    not path.is_file()
                    or path == self._SELF
                    or "__pycache__" in path.parts
                    or path.suffix not in self._TEXT_SUFFIXES
                ):
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if self._STALE_NAME in text:
                    hits.append(str(path.relative_to(REPO_ROOT)))
        for path in self._SCAN_FILES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if self._STALE_NAME in text:
                hits.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(hits, [], f"found stale '{self._STALE_NAME}' references in: {hits}")


class TestPublicPackagesShipPyTyped(unittest.TestCase):
    """templateConformance.md Gap 1.4: every package dir with a public API
    (an ``__init__.py`` defining ``__all__``) must ship ``py.typed``
    (PEP 561), so a dropped marker fails the gate instead of silently
    degrading downstream type-checking."""

    @staticmethod
    def _assigns_dunder_all(node: ast.stmt) -> bool:
        if not isinstance(node, ast.Assign):
            return False
        return any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        )

    def _public_package_dirs(self) -> list[Path]:
        public_dirs: list[Path] = []
        for init_file in SRC_DIR.rglob("__init__.py"):
            tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
            if any(self._assigns_dunder_all(node) for node in tree.body):
                public_dirs.append(init_file.parent)
        return public_dirs

    def test_every_public_package_has_py_typed(self) -> None:
        public_dirs = self._public_package_dirs()
        self.assertGreaterEqual(len(public_dirs), 1, f"expected public packages under {SRC_DIR}")

        missing = [
            str(pkg_dir.relative_to(REPO_ROOT))
            for pkg_dir in public_dirs
            if not (pkg_dir / "py.typed").is_file()
        ]
        self.assertEqual(missing, [], f"public package(s) missing py.typed: {missing}")


if __name__ == "__main__":
    unittest.main()
