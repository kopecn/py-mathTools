# ============================================================================
# CONFIG
# ============================================================================
.PHONY: help version checkCleanGit open-github \
	clean clean-build clean-artifacts clean-test \
	bump-patch bump-minor bump-major \
	check-uv install-uv list-uv \
	uv-bootstrap-pythons uv-bootstrap uv-sync uv-sync-headless uv-sync-dev uv-sync-release uv-sync-local uv-editable uv-refresh \
	uv-lint uv-format uv-typecheck uv-fullCheck \
	uv-test uv-test-all uv-test-matrix \
	uv-flush-cache uv-flush-envs uv-flush-pythons uv-flush-everything uv-nuke \
	uv-lifecycle-test \
	dev setup \
	installDev e refresh \
	test testInEnvCleanup testInEnvInstallFromSetup testInEnvRunPytest testInEnv \
	build validateBuild release-test release \
	nuke list

.DEFAULT_GOAL := help

# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Defaults (overridable via .env — the user-editable surface). Keep in sync with .env.
PYTHONS ?= 3.10 3.11 3.12 3.13
DEFAULT_PYTHON ?= 3.13
PYTHON ?= python3
VENV ?= .cleanroom-venv

# Quality-target paths. ROOT half has NO src/ — its Python lives in hooks/ + tests/
# (see GAPS.md §6). The template half overrides these to src/. Overridable via .env.
PY_SRC ?= hooks
PY_TESTS ?= tests
PY_EXAMPLES ?=
PY_ALL ?= $(PY_SRC) $(PY_TESTS) $(PY_EXAMPLES)


# Derived
# Tool runner for uv- quality/test recipes. `--extra dev` ensures ruff/mypy/pytest are
# resolved (and installed if missing) from the "[dev]" extra even on a FRESH checkout —
# no reliance on a pre-existing .venv, rather than the ambient PATH.
UV := uv run --no-project
PIP := $(PYTHON) -m pip
BUMPVERSION := bumpversion --allow-dirty
REPO := $(notdir $(CURDIR))
UNAME_S := $(shell uname -s)
HR := ========================================

# Guard: DEFAULT_PYTHON must be one of the versions we test against.
ifeq ($(filter $(DEFAULT_PYTHON),$(PYTHONS)),)
    $(error DEFAULT_PYTHON ($(DEFAULT_PYTHON)) is not in PYTHONS ($(PYTHONS)) — fix .env)
endif

# ============================================================================
# MARK: - Helpers · 
# ============================================================================

define uninstall_package_list
	@$(1) | while read pkg; do \
		[ -n "$$pkg" ] || continue; \
		$(PIP) uninstall -y "$$pkg" 2>&1 \
			|| echo "SKIPPED (system-managed): $$pkg"; \
	done
endef

define print_packages
	@echo "========================================"
	@echo "$(1)"
	@echo "========================================"
	@$(2) list 2>/dev/null || echo "No packages or pip not available"
	@echo
endef

# Roll HISTORY.md on a version bump: open a fresh dated section under
# [Unreleased] (folding the accumulated notes into the just-bumped version) and
# amend it into bump2version's commit so version + changelog move together.
# Keep-a-Changelog convention: the `## [Unreleased]` header is the anchor.
define roll_changelog
	@ver=$$($(MAKE) -s version); day=$$(date +%F); \
	awk -v v="$$ver" -v d="$$day" '\
		{ print } \
		/^## \[Unreleased\]/ && !seen { print ""; print "## [" v "] - " d; seen=1 }' \
		HISTORY.md > HISTORY.md.tmp && mv HISTORY.md.tmp HISTORY.md; \
	git add HISTORY.md; \
	case "$$(git log -1 --pretty=%s)" in \
		"Bump version:"*) git commit --amend --no-edit ;; \
		*) git commit -m "Roll HISTORY.md for v$$ver" ;; \
	esac
endef

# ============================================================================
# MARK: - HELP
# ============================================================================
help:  ## Show this help
	@echo "$(REPO) — make targets   (bare = pip · uv-… = uv path)"
	@echo "config: DEFAULT_PYTHON=$(DEFAULT_PYTHON)  PYTHONS=$(PYTHONS)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@ / {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
		/^[a-zA-Z0-9_%-]+:.*?## / {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)


# ============================================================================
# MARK: - COMMON · VERSION & GIT
# ============================================================================
##@ Common · Version & Git
version:  ## Display the current project version
	@$(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null \
		|| grep -m1 '^version' pyproject.toml | cut -d'"' -f2

checkCleanGit:  ## Guard: fail if the git working tree is dirty
	@[ -z "$$(git status --porcelain)" ] || \
		(echo "Working tree is dirty. Commit or stash changes first."; exit 1)

# Static pattern rule: all three documented parts share one recipe (`$*` = the
# part). Bump the version, then roll the changelog into the same commit.
bump-patch bump-minor bump-major: bump-%:  ## Bump version (patch|minor|major) + roll HISTORY.md
	$(BUMPVERSION) $*
	$(call roll_changelog)

open-github:  ## Open the GitHub repository in the default browser (macOS/Linux)
	@remote=$$(git remote | head -1); \
	[ -n "$$remote" ] || { echo "No git remote configured."; exit 1; }; \
	url=$$(git remote get-url "$$remote" | sed -e 's|git@github.com:|https://github.com/|' -e 's|\.git$$||'); \
	echo "Opening $$url"; \
	if [ "$(UNAME_S)" = "Darwin" ]; then open "$$url"; \
	elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$$url"; \
	else echo "No browser opener found; visit: $$url"; fi

# ============================================================================
# MARK: - COMMON · CLEAN
# Base cleanup targets used by install, test, and CI workflows.
# ============================================================================
##@ Common · Clean

clean: clean-build clean-artifacts clean-test ## Remove all build, cache, and test artifacts

clean-build: ## Remove packaging and distribution artifacts
	rm -rf build/ dist/ .eggs/
	find . \( -name '*.egg-info' -o -name '*.egg' \) -exec rm -rf {} +
	rm -f uv.lock

clean-artifacts: ## Remove Python bytecode and cache files
	find . \( \
		-name '*.pyc' -o \
		-name '*.pyo' -o \
		-name '*~' -o \
		-name '__pycache__' \
	\) -exec rm -rf {} +

clean-test: ## Remove test, coverage, and lint caches
	rm -f .coverage
	rm -rf \
		htmlcov/ \
		.pytest_cache/ \
		.mypy_cache/ \
		.ruff_cache/ \
		.tox/ \
		.nox/

# ============================================================================
# MARK: - UV · TOOLING
# ============================================================================
##@ UV · Tooling
check-uv:  ## Check if uv is installed (guard for all uv- targets)
	@command -v uv >/dev/null 2>&1 || { \
	  echo "ERROR: uv not found."; \
	  echo "  Install it with: make install-uv"; \
	  echo "  Or see: https://docs.astral.sh/uv/getting-started/installation/"; \
	  exit 1; }

install-uv:  ## Install uv (brew on macOS, installer script on Linux)
ifeq ($(UNAME_S),Darwin)
	@echo "Detected macOS - installing via Homebrew..."
	@command -v brew >/dev/null 2>&1 || { echo "ERROR: Homebrew not found. Install from https://brew.sh"; exit 1; }
	brew install uv
else ifeq ($(UNAME_S),Linux)
	@echo "Detected Linux - installing via official installer..."
	curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo ""
	@echo "NOTE: You may need to add ~/.local/bin to your PATH:"
	@echo '  export PATH="$$HOME/.local/bin:$$PATH"'
else
	@echo "Unsupported OS: $(UNAME_S)"
	@echo "Install manually: https://docs.astral.sh/uv/getting-started/installation/"
	@exit 1
endif
	@echo ""
	@echo "uv installed successfully:"
	@uv --version

list-uv: check-uv  ## List uv envs, installed Pythons, packages, and cache info
	@echo "$(HR)"; echo "UV VERSION"; echo "$(HR)"
	@uv --version
	@echo ""; echo "$(HR)"; echo "INSTALLED PYTHON VERSIONS"; echo "$(HR)"
	@uv python list --only-installed
	@echo ""; echo "$(HR)"; echo "PROJECT VIRTUAL ENVIRONMENTS"; echo "$(HR)"
	@ls -d .venv 2>/dev/null || echo "No .venv found"
	@ls -d .venvs/*/ 2>/dev/null || echo "No .venvs/ matrix environments found"
	@echo ""; echo "$(HR)"; echo "INSTALLED PACKAGES (.venv)"; echo "$(HR)"
	@uv pip list 2>/dev/null || echo "No packages or .venv not found"
	@echo ""; echo "$(HR)"; echo "UV CACHE INFO"; echo "$(HR)"
	@uv cache dir
	@du -sh $$(uv cache dir) 2>/dev/null || echo "Cache empty or not accessible"

# ============================================================================
# MARK: - UV · BOOTSTRAP & SYNC
# ============================================================================
##@ UV · Bootstrap & Sync
uv-bootstrap-pythons: check-uv  ## Install all configured Python versions via uv
	uv python install $(PYTHONS)

# Dependency model (BKM; see GAPS §5 / spec §6): pyproject.toml declares dependency
# NAMES ONLY — never version-pinned (only the application layer pins; module-level pins
# cause conflicts). The requirements*.txt files carry pins and git-based pointers, and
# every install path — pip AND uv — leans on them: `-r requirements.txt` then the
# editable self-install. No `uv.lock`, no `lock`/compile target.

uv-bootstrap: check-uv uv-bootstrap-pythons  ## Full bootstrap: pythons + venv + deps
	uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements.txt
	uv pip install -e ".[dev]"
	@echo ""
	@echo "Bootstrap complete. Run 'make uv-test-all' to validate."

uv-sync: check-uv  ## Sync all dependencies including dev (default dev workflow)
	@[ -d ".venv" ] || uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements.txt
	uv pip install -e ".[dev]"

uv-sync-headless: check-uv  ## Sync dependencies without dev/UI extras (headless deploy)
	@[ -d ".venv" ] || uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements.txt
	uv pip install -e "."

uv-sync-dev: check-uv  ## Sync dependencies with dev extras
	@[ -d ".venv" ] || uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements.txt
	uv pip install -e ".[dev]"

uv-sync-release: check-uv  ## Sync using tag-pinned release requirements (requirements-release.txt)
	@[ -d ".venv" ] || uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements-release.txt
	uv pip install -e "."

uv-sync-local: check-uv  ## Sync using local editable path overrides (requirements-local.txt)
	@[ -d ".venv" ] || uv venv --python $(DEFAULT_PYTHON)
	uv pip install -r requirements-local.txt
	uv pip install -e ".[dev]"

dev: uv-sync  ## One-command dev setup entrypoint (alias → uv-sync)
setup: dev  ## One-command dev setup entrypoint (alias → uv-sync)

uv-editable: check-uv  ## Install this package editable via uv (uv pip install -e .)
	uv pip install -e .

uv-refresh: check-uv  ## Clean cache + reinstall from requirements + upgrade editable dev
	uv cache clean
	uv pip install -r requirements.txt
	uv pip install --upgrade -e ".[dev]"

# ============================================================================
# MARK: - UV · QUALITY
# ============================================================================
##@ UV · Quality
uv-lint: check-uv  ## Run ruff linter (read-only; non-zero exit for CI)
	$(UV) ruff check $(PY_ALL)

uv-format: check-uv  ## Format code with ruff
	$(UV) ruff format $(PY_ALL)
# KEEP --unsafe-fixes: intentional, added after findings on 2026-06-25.
# Do NOT strip in cleanup/refactor passes — the unsafe autofixes here are relied
# upon deliberately. Removing it has regressed this target before.
	$(UV) ruff check --fix --unsafe-fixes $(PY_ALL)

uv-typecheck: check-uv  ## Strict type check with mypy
	$(UV) mypy $(PY_SRC) $(PY_TESTS) $(PY_EXAMPLES)

# ty (Astral's preview type-checker) is intentionally OUT for now (decision D1):
# it's pre-release and not wired into uv-fullCheck. Revisit when it stabilizes.
uv-fullCheck: check-uv uv-lint uv-typecheck uv-test  ## lint + typecheck + tests

# ============================================================================
# MARK: - UV · TEST
# ============================================================================
##@ UV · Test
# Depends on uv-sync so a fresh checkout never tests an empty/stale .venv (no
# false-green no-op): the [dev] extra is installed from pyproject before pytest runs.
uv-test: check-uv uv-sync  ## Run tests on DEFAULT_PYTHON (ensures a synced env first)
	$(UV) pytest

uv-test-all: check-uv  ## Run tests across all configured Python versions (.venvs/<ver>)
	@failed=""; \
	for py in $(PYTHONS); do \
		echo ""; \
		echo "========================================"; \
		echo "Testing Python $$py"; \
		echo "========================================"; \
		venv=".venvs/$$py"; \
		[ -d "$$venv" ] || uv venv --python $$py "$$venv"; \
		if ( . "$$venv/bin/activate" && \
		     uv pip install -q -e ".[dev]" && \
		     python -m pytest ); then \
			echo "PASS: Python $$py"; \
		else \
			echo "FAIL: Python $$py"; \
			failed="$$failed $$py"; \
		fi; \
	done; \
	echo ""; \
	echo "========================================"; \
	if [ -n "$$failed" ]; then \
		echo "FAILED VERSIONS:$$failed"; \
		echo "========================================"; \
		exit 1; \
	else \
		echo "ALL PYTHON VERSIONS PASSED"; \
		echo "========================================"; \
	fi

uv-test-matrix: uv-bootstrap-pythons uv-test-all  ## Ensure Pythons installed, then run all tests

# ============================================================================
# MARK: - UV · FLUSH / NUKE
# ============================================================================
##@ UV · Flush / Nuke

uv-flush-envs:  ## Remove all virtual environments (.venv + .venvs/<ver>)
	@echo ">> Removing virtual environments..."
	rm -rf .venv
	rm -rf .venvs
	rm -rf .venv-py*
	@echo "Virtual environments removed."

uv-flush-cache: check-uv  ## Clean uv cache
	@echo ">> Cleaning uv cache..."
	uv cache clean
	@echo "uv cache cleaned."

uv-flush-pythons:  ## Remove uv-managed Python installs (NUCLEAR)
	@echo "WARNING: This removes ALL uv-managed Python installations!"
	@echo "Location: ~/.local/share/uv/python"
	rm -rf ~/.local/share/uv/python
	@echo "uv-managed Pythons removed."

uv-flush-everything: clean uv-flush-envs uv-flush-cache  ## Full cleanup (keeps pythons)
	@echo "Environment flushed. Run 'make uv-flush-pythons' separately for global Pythons."

uv-nuke: uv-flush-everything  ## NUCLEAR: everything then prompt for Python removal
	@echo ""
	@echo ">> Running uv-nuke..."
	@$(MAKE) uv-flush-pythons
	@echo ""
	@echo "Environment nuked. Run 'make uv-bootstrap' to rebuild from scratch."

uv-lifecycle-test: uv-flush-everything uv-bootstrap uv-test-all  ## flush -> bootstrap -> test-all
	@echo ">> Lifecycle test complete"

# ============================================================================
# MARK: - PIP · INSTALL
# ============================================================================
##@ PIP · Install
# Ambient-pip fallback (prefer the uv- path). Both pip and uv lean on the requirements
# file (BKM rule 4): install -r requirements.txt, then self-install the editable
# package. No --break-system-packages / --force-reinstall: use a venv (make uv-sync)
# rather than fighting an externally-managed interpreter.
installDev: clean  ## Install dev dependencies with pip (-r requirements.txt + editable [dev])
	$(PIP) install -r requirements.txt
	$(PIP) install -e ".[dev]"

e:  ## Install this package in editable mode (pip install -e .)
	$(PIP) install -e .

refresh:  ## Refresh pip packages: reinstall from requirements + upgrade editable dev
	$(PIP) install -r requirements.txt
	$(PIP) install --upgrade -e ".[dev]"

# ============================================================================
# MARK: - PIP · TEST
# ============================================================================
##@ PIP · Test

test:  ## Run tests using the current Python environment
	pytest

testInEnvCleanup:  ## Delete the temporary venv ($(VENV))
	rm -rf $(VENV) || true

testInEnvInstallFromSetup: testInEnvCleanup  ## Create temp venv + install dev deps
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && \
	which python3 && \
	$(VENV)/bin/pip install ".[dev]"
	@echo "Virtual env can be activated with 'source $(VENV)/bin/activate'"

testInEnvRunPytest:  ## Run pytest inside the temporary venv
	. $(VENV)/bin/activate && \
	which $(PYTHON) && \
	$(PYTHON) -m pytest

testInEnv: clean testInEnvInstallFromSetup testInEnvRunPytest testInEnvCleanup  ## Full clean-room test
	@echo ">> testInEnv completed"

# ============================================================================
# MARK: - PIP · BUILD & RELEASE
# ============================================================================
##@ PIP · Build & Release
build: clean-build  ## Build sdist + wheel ($(PYTHON) -m build)
	@echo "Building package..."
	$(PYTHON) -m build

validateBuild: build  ## Validate build artifacts with twine
	@echo "Validating dist/ with twine..."
	$(PYTHON) -m twine check dist/*

release-test: checkCleanGit validateBuild  ## Dry-run publish to TestPyPI (clean tree only)
	@echo "Uploading $(REPO) v$$($(MAKE) -s version) to TestPyPI..."
	@$(PYTHON) -m twine upload --repository testpypi dist/*

# PyPI publishing is owned by CI, not this Makefile. Per the ci-cd spec, the
# pipeline is the single authoritative path to production — no manual, out-of-band
# uploads. `.github/workflows/tag-on-prod.yml` tags v<version> on push to `prod`;
# a publish-on-tag workflow promotes that artifact. `make release` therefore
# refuses to upload and prints the release procedure instead.
release: validateBuild  ## Refuse local upload; print the CI-driven release procedure
	@echo "Local PyPI upload is disabled — the pipeline is the authoritative publish path."
	@echo ""
	@echo "To release $(REPO) v$$($(MAKE) -s version):"
	@echo "  1. Bump the version (make bump-patch|bump-minor|bump-major) and merge to prod."
	@echo "  2. Push to prod → tag-on-prod.yml creates the v<version> tag."
	@echo "  3. The publish-on-tag workflow uploads to PyPI."
	@echo ""
	@echo "For a local pre-flight, use: make release-test (TestPyPI)."
	@exit 1

# ============================================================================
# MARK: - PIP · FLUSH / LIST
# ============================================================================
##@ PIP · Flush / List
# `nuke` is the INFERIOR pip fallback (Lesson 2): it per-package-uninstalls from
# the AMBIENT interpreter ($(PIP)). Prefer `make uv-flush-envs` — deleting the
# venv dir is the reliable flush primitive. Use this only when you're stuck in a
# non-deletable (e.g. system) env. Non-editable URL/VCS installs are skipped.
nuke: ## Per-package uninstall from ambient env (inferior — prefer uv-flush-envs)
	@echo "Uninstalling regular packages (skipping system-managed)..."
	$(call uninstall_package_list,$(PIP) freeze --exclude-editable | grep -v ' @ ')

	@echo "Uninstalling editable packages by name..."
	$(call uninstall_package_list,$(PIP) list --editable --format=freeze | cut -d= -f1)

	@echo "pip-nuke complete."

list: ## List pip packages in available environments
	$(call print_packages,SYSTEM PYTHON PACKAGES,$(PIP))

	@if [ -d ".venv" ]; then \
		echo "$(HR)"; \
		echo "VENV PACKAGES (.venv)"; \
		echo "$(HR)"; \
		.venv/bin/pip list 2>/dev/null || echo "No packages or pip not available"; \
		echo; \
	fi

	@for venv in .venvs/*; do \
		[ -d "$$venv" ] || continue; \
		echo "$(HR)"; \
		echo "VENV PACKAGES ($$venv)"; \
		echo "$(HR)"; \
		$$venv/bin/pip list 2>/dev/null || echo "No packages or pip not available"; \
		echo; \
	done
	