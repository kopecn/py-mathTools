"""Generator for ``successful_trajectories_multi_dof.json``.

Post-audit finding E-4 (``.claude/action-plan/56-test-closure-otg-oracles.md``
gap 1): the entire ``successful_trajectories.json`` / ``failed_trajectories.json``
classification corpus (1,784 cases) is 1-DOF, and 1-DOF ``calculate()`` calls
take the dedicated fast path at ``calculator_target.py:553`` (``if dofs == 1
and input_parameter.minimum_duration is None and not discrete_duration``),
which never invokes ``PositionThirdOrderStep2.get_profile`` -- it copies the
Step1-computed extremal profile directly. Step2 (the largest, hardest-to-port
module in the whole subsystem) therefore has zero oracle coverage from the
existing corpus.

**Method.** Reuses the existing 1-DOF ``successful_trajectories.json`` cases
(each already a validated, individually-solvable boundary condition) as raw
material: groups of 2/3/4 are drawn (without replacement, fixed-seed shuffle)
and combined into one multi-DOF ``InputParameter`` each, under the default
``Synchronization.TIME``. Synchronizing DOFs with different individual
optimal durations to the slowest one is exactly what forces the non-limiting
DOFs through ``PositionThirdOrderStep2`` (``calculator_target.py``'s "Time
Synchronization" loop) -- this is *why* Step2 exists in the Ruckig algorithm,
so it is the natural way to reach it, rather than hand-authoring boundary
conditions.

Each combination is verified against ``Otg.calculate`` at generation time and
only kept if it returns a non-error ``Result`` -- mirroring how the original
``successful_trajectories.json`` corpus is itself a curated "known-good"
set, not an assertion that every random combination of independently-valid
1-DOF cases remains solvable once synchronized (some do fail, e.g. when the
combination happens to trip ``ERROR_SYNCHRONIZATION_CALCULATION``; empirically
0/450 did in the run that produced the committed file, but the filter is kept
so the generator stays correct if the source corpus or grouping changes).

**Reproducibility (otg.md-adjacent design constraint 4).** Fixed seed
``_SEED``; deterministic shuffle of the source corpus' indices; deterministic
group sizes and counts. Re-running this script against an unchanged
``successful_trajectories.json`` reproduces ``successful_trajectories_multi_dof.json``
byte-for-byte.

Run: ``python tests/otg/data/generate_multi_dof_corpus.py`` from the repo
root (with ``src/`` on ``sys.path``, e.g. via the project's ``.venv``).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent
_SOURCE = _DATA_DIR / "successful_trajectories.json"
_OUTPUT = _DATA_DIR / "successful_trajectories_multi_dof.json"

_SEED = 20260722
_GROUP_SIZES = (2, 3, 4)
_GROUPS_PER_SIZE = 150


def _combine(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge ``len(cases)`` 1-DOF classification-corpus entries into one
    multi-DOF entry (default ``Position``/``Time``/``Continuous``, all DOFs
    enabled -- the ordinary multi-DOF configuration)."""
    dofs = len(cases)

    def field(name: str) -> list[float]:
        return [case[name][0] for case in cases]

    return {
        "degreesOfFreedom": dofs,
        "controlInterface": "Position",
        "synchronization": "Time",
        "durationDiscretization": "Continuous",
        "currentPosition": field("currentPosition"),
        "currentVelocity": field("currentVelocity"),
        "currentAcceleration": field("currentAcceleration"),
        "targetPosition": field("targetPosition"),
        "targetVelocity": field("targetVelocity"),
        "targetAcceleration": field("targetAcceleration"),
        "maxVelocity": field("maxVelocity"),
        "maxAcceleration": field("maxAcceleration"),
        "maxJerk": field("maxJerk"),
        "intermediatePositions": [],
        "enabled": [True] * dofs,
    }


def generate() -> list[dict[str, Any]]:
    # sys.path setup so this script is runnable standalone.
    repo_root = _DATA_DIR.parents[2]
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from math_tools.otg.input_parameter import InputParameter
    from math_tools.otg.otg import Otg
    from math_tools.otg.output_parameter import OutputParameter

    with _SOURCE.open() as f:
        source = json.load(f)

    rng = random.Random(_SEED)
    indices = list(range(len(source)))
    rng.shuffle(indices)

    combos: list[dict[str, Any]] = []
    pos = 0
    for size in _GROUP_SIZES:
        for _ in range(_GROUPS_PER_SIZE):
            group = indices[pos : pos + size]
            pos += size
            combos.append(_combine([source[i] for i in group]))

    kept: list[dict[str, Any]] = []
    rejected = 0
    for combo in combos:
        inp = InputParameter.from_dict(combo)
        dofs = inp.degrees_of_freedom
        otg = Otg(0.01, dofs=dofs)
        output = OutputParameter(dofs=dofs)
        result = otg.calculate(inp, output)
        if result >= 0:
            kept.append(combo)
        else:
            rejected += 1

    print(f"generated {len(combos)} combinations, kept {len(kept)}, rejected {rejected}")
    return kept


if __name__ == "__main__":
    cases = generate()
    with _OUTPUT.open("w") as f:
        json.dump(cases, f, indent=2)
        f.write("\n")
    print(f"wrote {len(cases)} cases to {_OUTPUT}")
