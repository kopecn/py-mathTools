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
DSP_ROOT = MATH_TOOLS_ROOT / "waveforms" / "dsp"
_DSP_ALLOWED_SIBLING_MODULES = {"_protocol", "_common"}


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


def _dsp_sibling_imports(module_path: Path) -> set[str]:
    """Sibling ``dsp/_*`` module names ``module_path`` imports (its own name excluded),
    in both absolute (``math_tools.waveforms.dsp._foo``) and relative
    (``from ._foo import ...`` / ``from . import _foo``) forms."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0 and node.module == "math_tools.waveforms.dsp":
            found.update(alias.name for alias in node.names)
        elif (
            node.level == 0 and node.module and node.module.startswith("math_tools.waveforms.dsp.")
        ):
            found.add(node.module.split(".")[-1])
        elif node.level >= 1:
            if node.module:
                found.add(node.module.split(".")[-1])
            else:
                found.update(alias.name for alias in node.names)
    found -= _DSP_ALLOWED_SIBLING_MODULES
    found.discard(module_path.stem)
    return found


def test_dsp_mixins_do_not_import_sibling_mixins() -> None:
    """waveformDsp.md §Compliance 2 / §Organization: each ``dsp/_*.py`` mixin module
    imports scipy/numpy plus ``_protocol``/``_common`` only -- no sibling mixin
    imports (shared helpers live in ``dsp/_common.py``).

    Guarded to skip if ``waveforms/dsp`` does not exist yet so this enforcement is
    inherited for free (mirrors ``test_otg_does_not_import_numpy``'s pattern).
    """
    if not DSP_ROOT.is_dir():
        return

    violations: dict[str, set[str]] = {}
    for module_path in DSP_ROOT.glob("_*.py"):
        # `_*.py` also matches `__init__.py` (leading `__` starts with `_`), but the
        # package `__init__` is not a mixin module -- from chunk 30 onward it is
        # expected to import every mixin to re-export them (waveformDsp.md
        # §Organization), which is exactly the pattern this test forbids for the
        # mixin modules themselves.
        if module_path.name == "__init__.py":
            continue
        if module_path.stem in _DSP_ALLOWED_SIBLING_MODULES:
            continue
        sibling_imports = _dsp_sibling_imports(module_path)
        if sibling_imports:
            violations[str(module_path.relative_to(SRC_ROOT))] = sibling_imports

    assert not violations, (
        "dsp mixin modules must import only _protocol/_common from within "
        f"waveforms/dsp/, but found sibling-mixin imports: {violations}"
    )


def test_math_tools_is_scanned() -> None:
    """Guard against the scan silently finding zero files (e.g. a bad glob root)."""
    scanned = list(MATH_TOOLS_ROOT.rglob("*.py"))
    assert len(scanned) >= 1, f"expected at least 1 module under math_tools/, found {scanned}"
