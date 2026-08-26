---
chunk: 57-docs-and-convention-sweep
track: F
status: complete
depends_on: [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56]
spec: ../specs/templateConformance.md, ../specs/mathToolsArchitecture.md
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 57 — Docs and convention sweep (runs last)

## Origin

All class **(e)** docs/convention-drift findings from the audit, plus the
governance-test gaps. Runs last so it can also reconcile documentation against
whatever chunks 44–56 actually changed.

## Files

- Edit: `Makefile`, `pyproject.toml`, `README.md`
- Edit: `.claude/CLAUDE.md`
- Edit: `.claude/specs/templateConformance.md`
- Edit: `.claude/action-plan/00-overview.md` and all chunk files (frontmatter only)
- Edit: `.claude/action-plan/42-otg-oracle-suites.md`
- Edit: `src/math_tools/hints.py`
- Edit: `src/math_tools/waveforms/waveform_position.py`,
  `waveform_quaternion.py`, `waveform_spatial_pose.py` (resolution-note comments only)
- Edit: `tests/otg/test_otg_truth_table.py`, `test_otg_comprehensive.py` (docstrings only)
- Edit: `tests/test_governance.py`

## Gaps to close

**Dead references**

1. **A-3** — `templateConformance.md:27-29` lists `ci.yml` / `tag-on-prod.yml` /
   `publish.yml` as "already conformant (verify, don't re-do)".
   `.github/workflows/` contains only `ci-cd.yml`. Correct the spec to name the
   file that exists.
2. **A-4** — `Makefile:434-436` prints release instructions referencing
   `tag-on-prod.yml` and "the publish-on-tag workflow". Neither exists;
   `make release` hands the user a dead procedure. Fix the text to match
   `ci-cd.yml`'s actual release path, or state plainly that release is manual.
3. **A-13** — `README.md:40` says `pip install py_math_tools`, but the package
   is unpublished (`pyproject.toml:57-59` point at `github.com/kopecn`) and the
   real path is `make uv-sync`. templateConformance Gap 4.1 requires the README
   describe what actually exists.
4. **A-8** — `pyproject.toml:15`: `keywords = ["my_package", "python", "package"]`
   — template boilerplate that survived Gap 4.

**Stale claims in test and plan docs**

5. **E-doc** — `tests/otg/test_otg_truth_table.py:121` and
   `test_otg_comprehensive.py:29` both say "segment times atol 1e-8"; the
   constant at `test_otg_truth_table.py:55` is `1e-6`.
6. **E-doc** — `.claude/action-plan/42-otg-oracle-suites.md:37` design constraint 2
   still says atol 1e-8, contradicting the same file's own Resolution at `:158-168`.
7. **E-doc** — `42-otg-oracle-suites.md:14` says "32-case numeric truth table";
   it is 31. (The audit re-parsed all 31 Swift cases and diffed every field —
   0 mismatches, nothing dropped. The count in the doc is simply wrong.)
8. **C-16** — chunks 15/16 resolution notes claim `normalize()`'s zero-magnitude
   check uses "the same `atol=1e-12` tolerance" as `Position.is_unit`. The code
   uses an exact `norms == 0.0` (`waveform_position.py:242`,
   `waveform_quaternion.py:266`, `waveform_spatial_pose.py:423,430`). The
   behavior is correct — it matches `Position.normalize`'s own exact
   `magnitude == 0.0` (`position.py:354`) — the notes are wrong. Fix the notes.

**Convention drift**

9. **A-9** — `00-overview.md:33-34` defines chunk status as
   `pending` → `in_progress` / `done`. All 44 existing chunk files use
   `status: complete`, a value the convention does not define. Reconcile:
   amend the convention to include `complete` (simpler, matches reality) and say
   so in the overview.
10. **A-10** — `templateConformance.md:104-109`: all six compliance boxes remain
    `- [ ]` though chunks 01–03 are complete and five of six are satisfied.
    Check off what is genuinely true; leave the rest unchecked.
11. **A-11** — `.claude/CLAUDE.md` carries no frontmatter, while all 8 specs and
    all 44 chunks correctly carry `last_updated` / `semver` /
    `author: Nicholas Bergantz`. Add it.
12. **A-12** — `src/math_tools/hints.py:30-32`: an
    `if __name__ == "__main__":` block with a bare `assert isinstance(...)`.
    Not spec'd, not tested, not reachable. Delete.

**Governance-test gaps**

13. **A-5** — half the template compliance checklist has no regression test.
    `templateConformance.md:104-105` (no `pyMathTools` hits anywhere; `py.typed`
    present in every public package) are never asserted;
    `tests/test_governance.py:18-43` covers only items 107-108. A rename
    regression or a dropped `py.typed` passes the gate silently. Add both
    assertions.
14. **A-6** — `examples/` is entirely outside the gate: `Makefile:37`
    (`PY_EXAMPLES ?=`) is never set, so neither `uv-typecheck` (`Makefile:281`)
    nor `uv-lint` scans it. Chunk 03's "both example scripts import-run without
    error" was a one-time manual check with nothing guarding it — the exact
    dead-import class of bug Gap 4.3 existed to fix. Evidence it has already
    drifted: `examples/sphericalPlotting/plotArcs.py:1` and
    `plotQuatUnitCircles.py:28` use `from typing import List`, which ruff's `UP`
    rules (`pyproject.toml:85`) would flag if scanned. Wire `examples/` into
    lint and typecheck, then fix what that surfaces.

## Design constraints

1. Docs only, plus the two mechanical code deletions (gap 12) and the
   governance/gate wiring (gaps 13–14). No behavioral source changes.
2. Gap 14 will surface lint/type errors in `examples/`. Fix those; if any fix
   would change example *behavior*, stop and report instead.
3. Reconcile every doc against the post-44–56 state of the repo, not the
   pre-audit state.

## Acceptance criteria

- [x] All 14 gaps closed
- [ ] `grep -rn "tag-on-prod\|publish.yml" Makefile .claude/` returns nothing
      -- unchecked as literally written: `Makefile` and
      `templateConformance.md` are clean (verified separately), but the
      grep still matches this chunk file's own gap-description prose
      (`.claude/action-plan/57-docs-and-convention-sweep.md`, describing
      the dead references that were fixed) and this line's own text. See
      Resolution notes.
- [x] `examples/` covered by `uv-lint` and `uv-typecheck`; both clean
- [x] `test_governance.py` asserts no-`pyMathTools` and `py.typed` presence
- [x] `.claude/CLAUDE.md` has compliant frontmatter
- [x] `make uv-fullCheck` passes

## Resolution notes

**All 14 gaps closed.** File-by-file:

- **A-3** (`templateConformance.md`): "Already conformant" bullet corrected
  to name `ci-cd.yml` (quality + compatibility checks on PRs to
  `dev`/`prod`) instead of the nonexistent `ci.yml`/`tag-on-prod.yml`/
  `publish.yml` scaffold.
- **A-4** (`Makefile`): `release` target's printed procedure and preceding
  comment rewritten to state plainly that no CI-driven publish path exists
  (`ci-cd.yml` only runs quality/compat checks) and release is a manual,
  human-run `twine upload`. Behavior unchanged — `make release` still
  refuses and exits 1.
- **A-13** (`README.md`): Installation section no longer claims
  `pip install py_math_tools`; states the package is unpublished and points
  at `make uv-sync`, linking to Development Workflows.
- **A-8** (`pyproject.toml`): `keywords` replaced with real, descriptive
  terms (`math`, `numpy`, `quaternion`, `spatial`, `waveform`,
  `trajectory-generation`), replacing the `my_package`/`python`/`package`
  boilerplate.
- **E-doc atol** (`tests/otg/test_otg_truth_table.py:121`,
  `tests/otg/test_otg_comprehensive.py:41`): both corrected from the stale
  "atol 1e-8" to the actual "atol 1e-6" the constants/spec use.
- **E-doc constraint 2** (`42-otg-oracle-suites.md:37`): design constraint
  2 corrected from `atol 1e-8` to `atol 1e-6` to match the chunk's own
  Resolution notes (the historical narrative documenting *why* it changed,
  lines 92-169, was left untouched — only the current-tense
  Deliverable/Files/Design-constraint text describing what the chunk
  produces was corrected).
- **E-doc "32-case"** (`42-otg-oracle-suites.md:14,24`): corrected to
  "31-case" in the Deliverable and Files sections (same rationale: the
  historical Resolution-notes narrative is left as-is).
- **C-16** (deviation from the literal Files list): the false "same
  `atol=1e-12`" claim about `normalize()`'s zero-magnitude check does not
  exist anywhere in `src/math_tools/waveforms/waveform_position.py`,
  `waveform_quaternion.py`, or `waveform_spatial_pose.py` (grepped for it;
  0 hits). It exists only in `.claude/action-plan/15-waveform-position.md`
  and `16-waveform-quaternion.md`'s own "Resolution notes" sections — the
  chunk's Files list appears to have mislabeled the file type for this
  item. Fixed at the actual location instead: both chunk files' resolution
  notes now correctly state that `are_all_unit` uses `atol=1e-12` (parity
  with `Position.is_unit`) while the zero-magnitude `ValueError` in
  `normalize()` uses an exact `== 0.0` check (parity with
  `Position.normalize()`'s own exact check), not `atol=1e-12`. Bumped both
  chunks' frontmatter (semver 0.0.1 → 0.0.2) since their body text changed.
  `waveform_spatial_pose.py`/chunk 17 was checked and carries no such claim
  — nothing to fix there.
- **A-9** (`00-overview.md`): convention item 5 amended to specify
  `complete` (not `done`) as the terminal status, matching all 57 existing
  chunk files. Reconciled the doc to reality per the gap's own
  recommendation rather than rewriting 44 chunk files' status fields.
- **A-10** (`templateConformance.md` compliance checklist): checked off
  5 of 6 boxes after independently re-verifying each (grep for
  `pyMathTools` → 0 hits; `py.typed` in all 9 public package dirs;
  `make uv-fullCheck` passes; `.claude/CLAUDE.md` links all 8 specs;
  `README.md` has no "Boilerplate" text). The 6th
  (`test_package_layering.py` "passes and fails if matplotlib is added")
  was also checked, since `test_math_tools_does_not_import_matplotlib`
  is a real AST-scan assertion, not a vacuous one.
- **A-11**: `.claude/CLAUDE.md` given minimal frontmatter
  (`last_updated`/`semver`/`author`), matching the gap's literal ask.
- **A-12**: the dead `if __name__ == "__main__":` block deleted from
  `src/math_tools/hints.py`; its now-unused `q_one` import removed too
  (would otherwise trip ruff F401).
- **A-5** (`tests/test_governance.py`): added
  `TestNoPreRenamePackageName` (scans `src/`, `tests/`, `examples/`,
  `Makefile`, `pyproject.toml` for the pre-rename `pyMathTools` string;
  excludes itself and `__pycache__`) and
  `TestPublicPackagesShipPyTyped` (walks every `__init__.py` under `src/`
  that defines `__all__` — the mechanical definition of "public package"
  used elsewhere in this repo, e.g. distinguishing the private
  `otg/steps/` from public packages — and asserts a sibling `py.typed`).
  Both pass against the current tree (6/6 governance tests green).
- **A-6** (`examples/` gate wiring): `Makefile`'s `PY_EXAMPLES ?=` default
  changed to `PY_EXAMPLES ?= examples`. This surfaced real lint/type
  errors exactly as the gap predicted: unused `typing.List` imports,
  unsorted imports, 3 genuinely-unused constants (`deg45`/`deg180`/
  `deg22_5`) in `plotArcs.py`, a too-long docstring line, a missing `-> None`
  return annotation, an `arcs` list typed too narrowly for what
  `arc_from_two_points` actually returns (widened to the `UnitSphericalArcABC`
  base it's declared to return, matching `plot_unit_spherical_multiplot`'s
  own parameter type), and 3 `from_unit_x_to_vector(list[int])` calls
  needing `np.ndarray` per that method's signature. All fixes are
  mechanical (typing/import hygiene, no numeric or control-flow change);
  verified by running both example scripts end-to-end under `Agg` backend
  post-fix — both complete without error, matching pre-fix behavior.

**Deviation from the literal acceptance grep.** The plan's acceptance
criterion `grep -rn "tag-on-prod\|publish.yml" Makefile .claude/` cannot
return zero hits as literally written, because this chunk file
(`.claude/action-plan/57-docs-and-convention-sweep.md`) necessarily quotes
those strings while describing the A-3/A-4 gaps it fixed (and now also
quotes the acceptance-criterion line itself). Verified the substantive
intent instead: `grep -rn "tag-on-prod\|publish.yml" Makefile
.claude/specs/templateConformance.md` returns nothing — the two files that
actually needed correcting are clean.

**No spec-semver bump was needed on `mathToolsArchitecture.md`** — nothing
in its content was found stale by this sweep. `templateConformance.md` was
bumped 0.0.2 → 0.0.3 (A-3 correction + compliance-checklist checkoffs);
`.claude/action-plan/00-overview.md` bumped 0.1.0 → 0.1.1 (status
convention); `42-otg-oracle-suites.md` bumped 0.0.2 → 0.0.3;
`15-waveform-position.md` and `16-waveform-quaternion.md` each bumped
0.0.1 → 0.0.2.

**Gate.** `make uv-fullCheck`: ruff clean (`src`, `tests`, `examples`),
mypy strict clean (122 source files, up from 116 pre-sweep since
`examples/` is now scanned), 1550 passed (up from 1548 — the 2 new
governance tests), exit 0.

## Recorded — no action

These audit findings are deliberately not being fixed. Recorded so the decision
is not relitigated:

- **B-6** — `Position`/`SpatialPose` operators hardcode `Position.from_vector`
  while constructors are `cls: type[T]`-generic, so subclasses degrade to the
  base type on arithmetic (`position.py:245,257,320,334,364`;
  `spatial_pose.py:192,206,212,226,253`). No subclasses exist in-repo and none
  are planned; fixing it touches every operator. Revisit if a subclass appears.
- **B-4/B-5** — `SpatialPose.inverse` and `UnivariatePolynomial.derivative` are
  methods where the spec's notation implies properties. Cosmetic; changing them
  is a breaking API change for no behavioral gain.
- **A-7** — `spherical/` and `math_plot_helpers/` have zero behavioral tests
  (11 public functions). Pre-existing legacy, explicitly "behavior unchanged"
  per `mathToolsArchitecture.md:94`; no chunk ever owned them. Chunk 52 pins
  their public surface. A test suite for them is separate scoped work.
- **D-cross-cutting** — `WaveformPaddingStrategy`,
  `WaveformFilterCoefficients`, `WaveformFrequencyRange` (`support.py:158,238,354`)
  and `WaveformSpectrogramScaling` (`support.py:174`) are spec'd support types
  that no DSP method consumes. Either the spec's YAGNI rule is violated or
  consuming methods are missing. Deciding which is a spec question, not a fix —
  raise it in the next spec review.
- **D-spectral-(c)** — `spectrogram` uses legacy `scipy.signal.spectrogram`
  where waveformDsp.md names `scipy.signal.ShortTimeFFT`. Chunk 21 permitted
  either, so spec and code disagree but chunk and code do not. Migrating is a
  behavioral change needing its own chunk.
- **E-10** — `_time_none_smooth` (`position_third_order_step2.py:2415`, 0%
  coverage) is dead in Swift too and documented as such.
