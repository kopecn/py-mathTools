"""Dependency-direction tests for the ``math_tools`` / ``math_plot_helpers`` split.

Per templateConformance.md §Gap 5, the layering contract is:

- ``math_tools`` never imports ``math_plot_helpers`` or ``matplotlib``.
- ``math_plot_helpers`` may import ``math_tools``.
- Only ``math_plot_helpers`` imports ``matplotlib``.
- ``math_tools.otg`` (once it exists) never imports ``numpy`` (real-time
  control-loop constraint; guarded to skip until the package exists so OTG
  chunks inherit enforcement for free).

Enforced via a static AST scan (no imports executed) of every module under
``src/``, mirroring py-foundationTools' ``tests/test_package_layering.py``.
"""

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
MATH_TOOLS_ROOT = SRC_ROOT / "math_tools"
MATH_PLOT_HELPERS_ROOT = SRC_ROOT / "math_plot_helpers"
OTG_ROOT = MATH_TOOLS_ROOT / "otg"


def _imported_top_level_names(module_path: Path) -> set[str]:
    """Return the top-level package name of every module imported by ``module_path``."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # node.level > 0 is a relative import (`from . import x`); it can only
            # resolve within the same package, so it is never forbidden.
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_math_tools_does_not_import_math_plot_helpers() -> None:
    violations: dict[str, set[str]] = {}
    for module_path in MATH_TOOLS_ROOT.rglob("*.py"):
        imported = _imported_top_level_names(module_path) & {"math_plot_helpers"}
        if imported:
            violations[str(module_path.relative_to(SRC_ROOT))] = imported

    assert not violations, (
        "math_tools must not import math_plot_helpers (one-way dependency: "
        f"math_plot_helpers -> math_tools), but found: {violations}"
    )


def test_math_tools_does_not_import_matplotlib() -> None:
    violations: dict[str, set[str]] = {}
    for module_path in MATH_TOOLS_ROOT.rglob("*.py"):
        imported = _imported_top_level_names(module_path) & {"matplotlib"}
        if imported:
            violations[str(module_path.relative_to(SRC_ROOT))] = imported

    assert not violations, (
        "math_tools must not import matplotlib (matplotlib is "
        f"math_plot_helpers-only), but found: {violations}"
    )


def test_only_math_plot_helpers_imports_matplotlib() -> None:
    violations: dict[str, set[str]] = {}
    for module_path in SRC_ROOT.rglob("*.py"):
        if MATH_PLOT_HELPERS_ROOT in module_path.parents:
            continue
        imported = _imported_top_level_names(module_path) & {"matplotlib"}
        if imported:
            violations[str(module_path.relative_to(SRC_ROOT))] = imported

    assert not violations, f"only math_plot_helpers may import matplotlib, but found: {violations}"


def test_otg_does_not_import_numpy() -> None:
    """OTG is a real-time control loop; it must not depend on numpy.

    Guarded to skip if ``math_tools/otg`` does not exist yet so this
    enforcement is inherited for free once the OTG chunks land.
    """
    if not OTG_ROOT.is_dir():
        return

    violations: dict[str, set[str]] = {}
    for module_path in OTG_ROOT.rglob("*.py"):
        imported = _imported_top_level_names(module_path) & {"numpy"}
        if imported:
            violations[str(module_path.relative_to(SRC_ROOT))] = imported

    assert not violations, f"math_tools.otg must not import numpy, but found: {violations}"


def test_math_tools_is_scanned() -> None:
    """Guard against the scan silently finding zero files (e.g. a bad glob root)."""
    scanned = list(MATH_TOOLS_ROOT.rglob("*.py"))
    assert len(scanned) >= 1, f"expected at least 1 module under math_tools/, found {scanned}"
