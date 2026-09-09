---
version: 1.0
type: specification
name: templateConformance
purpose: Bring py-MathTools into full conformance with the py-foundationTools template conventions
spec: TemplateConformance
scope: project
status: draft
applies_to: pyproject.toml, requirements.txt, Makefile, .env, .github/, .claude/, src/, README.md
last_updated: 2026-08-26
semver: 0.1.1
author: Nicholas Bergantz
---

# Template Conformance

> Sibling of [mathToolsArchitecture.md](mathToolsArchitecture.md). This spec states what "conformant to the py-foundationTools template" means for this repo; it does not copy that repo's content. The authoritative template reference is the py-foundationTools release selected by `requirements.txt`.
>
> The migration that first brought this repo into conformance is recorded in [`../archive/math-tools-port/`](../archive/math-tools-port/00-overview.md). Reproduced dependency-resolution evidence is held in [the 2026-08-26 findings](../findings/2026-08-26-spherical-spatial-packaging.md).

## Package and module naming

- Import packages are snake_case: `math_tools` and `math_plot_helpers` under `src/`.
- Module filenames are snake_case; class names are not affected by this rule.
- The distribution name is `py_math_tools` and is independent of the import package names.
- Every package directory exposing a public API ships `py.typed`.
- Package discovery is driven by `package-dir = {"" = "src"}`; no explicit `packages` enumeration is maintained.
- Tooling configuration that names packages or paths resolves to the names above.

## Dependency declaration model

This model is the repo BKM: only the application layer pins, so module-level pins and version-control URLs in `pyproject.toml` are prohibited.

1. `pyproject.toml` `dependencies` declares **names only** — no version specifier, no `@`, no `git+` URL.
2. `requirements*.txt` carries every pin and version-control pointer. It is the authoritative resolution source for `pyFoundationTools`.
3. No lockfile is committed.

## Dependency resolvability

### Pin immutability

The `pyFoundationTools` pointer in `requirements.txt` SHALL name an immutable, remotely reachable ref — a release tag or a full 40-character commit SHA. A branch name SHALL NOT be used.

The pinned ref SHALL supply the full import surface this repo depends on:

- `foundation_abc.math.{mathEnums, precisionTimeABC, spatialABCs, sphericalABCs, waveformABCs}`
- `foundationTypes.mathTypes.MathTypes.{PositionType, QuaternionWaveformType, PositionWaveformType, PrecisionTimeIntervalType, PrecisionTimestampType, ScalarWaveformType, SpatialTransformType, SpatialTransformWaveformType, UnitSphericalArcType, UnitSphericalSmallCircleType}`

The declared environment SHALL be reproducible from `requirements.txt` alone, independently of any environment already installed.

### Install-path parity

Every install path that runs tests SHALL resolve `pyFoundationTools` from `requirements.txt`, installing the requirements file before the editable self-install. No target that installs the package's own extras without `requirements.txt` may run tests.

Where two CI jobs install by different paths, both SHALL resolve `pyFoundationTools` to the same version.

### Distribution consumption

Built artifacts carry only the names-only requirement from `pyproject.toml` metadata; `requirements.txt` is not part of wheel metadata. Resolving `pyFoundationTools` is therefore the consumer's responsibility — a consequence of §Dependency declaration model, not an exception to it.

`README.md` §Installation SHALL state that installing the distribution requires supplying a `pyFoundationTools` source — the `requirements.txt` pointer, a private index, or an already-installed foundation — and SHALL give a working command. Whether py-foundationTools is published to an index is an upstream decision this spec does not make.

## Environment currency

Verification results are evidence only about the environment that produced them. An environment SHALL match the current `requirements.txt` pin for its results to bear on this repo's conformance.

## Governance artifacts

1. `.claude/CLAUDE.md` states this repo's role, package map, and gate command, and links every spec under `.claude/specs/`. It references specs and does not duplicate their content. Publishing a new spec includes adding its link here.
2. `.claude/specs/` holds the spec set.
3. `.claude/findings/` holds reproduced defect evidence and other non-normative observations.
4. `.claude/archive/` holds completed chunk sets.

## README and metadata

1. `README.md` follows the template's section shape: title → Features → Installation → Quick Start → Development Workflows → Requirements, and describes only what exists.
2. `pyproject.toml` `description` describes this package, not boilerplate.
3. Everything under `examples/` imports real module paths and runs against the installed package.

## Layering enforcement

`tests/test_package_layering.py` asserts, by AST scan of `src/`:

- `math_tools` never imports `math_plot_helpers` or `matplotlib`.
- `math_plot_helpers` may import `math_tools`.
- Only `math_plot_helpers` imports `matplotlib`.

The test fails if a `matplotlib` import is added to any `math_tools` module.

## Conformance criteria

Observable properties of a conformant repo:

1. Import package names match §Package and module naming, and every public package ships `py.typed`.
2. `.claude/CLAUDE.md` links every `*.md` under `.claude/specs/`.
3. `README.md` carries no boilerplate stub text, and its §Installation satisfies §Distribution consumption.
4. The layering test passes, and fails when a `matplotlib` import is introduced into `math_tools`.
5. `pyproject.toml` `dependencies` contains no version specifier, `@`, or `git+` URL.
6. The `requirements.txt` `pyFoundationTools` pointer names a tag or full commit SHA that resolves against the remote.
7. An environment built from `requirements.txt` alone supplies every symbol in §Pin immutability.
8. All test-running install paths resolve `pyFoundationTools` to the same version.
