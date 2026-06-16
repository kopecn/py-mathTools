.PHONY: clean cleanTest cleanArtifacts cleanBuild docs help test testInEnv \
	testInEnvInstallFromSetup testInEnvRunPytest testInEnvCleanup \
	dist release install devInstall flushPip build version tag

.DEFAULT_GOAL := help

# Load anything from the .env file if it exists
ifneq (,$(wildcard .env))
	include .env
	export
endif

VERSION=v$(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
PIP := $(PYTHON) -m pip

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

bumpPatch:
	bump2version patch

bumpMinor:
	bump2version minor

bumpMajor:
	bump2version major

clean: cleanBuild cleanArtifacts cleanTest  ## Remove all build, Python, and test-related artifacts

cleanBuild:  ## Delete build-related directories and files
	rm -rf build/ dist/ .eggs/
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '*.egg' -exec rm -rf {} +

cleanArtifacts:  ## Remove Python bytecode and cache files
	find . \( -name '*.pyc' -o -name '*.pyo' -o -name '*~' \) -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

cleanTest:  ## Remove test outputs and coverage data
	rm -f .coverage
	rm -rf htmlcov/ .pytest_cache

lint:  ## Run linters like pylint or ruff
	pylint src/

format:  ## Format code with black
	black src/

typecheck:  ## Type check with mypy
	mypy src/

fullCheck: lint typecheck test  ## Run full quality and test checks

validateTomlSetup:  ## Check if pyproject.toml and setup are valid
	$(PYTHON) -m build --sdist --wheel --outdir /tmp/test_build

test:  ## Run tests using the current Python environment
	pytest

testInEnv: clean testInEnvInstallFromSetup testInEnvRunPytest testInEnvCleanup  ## Run tests in a temporary virtual environment

testInEnvInstallFromSetup: testInEnvCleanup  ## Set up temporary venv and install dev dependencies
	$(PYTHON) -m venv $(VENV) && \
	. $(VENV)/bin/activate && \
	which python3 && \
	$(PYTHON) -m pip install ".[personal_repos,develop]"
	@echo "Virtual env can be activated with 'source $(VENV)/bin/activate'"

testInEnvRunPytest:  ## Run tests inside the temporary virtual environment
	. $(VENV)/bin/activate && \
	which $(PYTHON) && \
	$(PYTHON) -m pytest

testInEnvCleanup:  ## Delete the temporary virtual environment
	rm -rf $(VENV) || true

checkVenv:
	@test "$$VIRTUAL_ENV" != "" || (echo "Not in a virtualenv!"; exit 1)

dist: clean  ## Create source and wheel distributions
	$(PYTHON) -m build
	ls -l dist

build:  ## Build project to check packaging without uploading
	rm -rf build dist
	$(PYTHON) -m build

version:  ## Display the current project version
	@echo "Current version is $(VERSION)"

tag: checkCleanGit version  ## Create and push a git tag
	@echo "Tagging version $(VERSION)"
	git tag -a $(VERSION) -m "Creating version $(VERSION)"
	git push origin $(VERSION)

checkCleanGit:
	@git diff-index --quiet HEAD -- || (echo "Git working directory not clean" && exit 1)

releaseTest: dist  ## Upload to TestPyPI
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

release: dist  ## Upload the distribution package to PyPI
	set -euo pipefail && twine upload dist/*

install: clean  ## Install the package in editable mode (local dev install)
	$(PIP) install -e .

devInstall: clean  ## Install development dependencies
	$(PIP) install -e .[develop]
	$(PIP) install pytest pylint black mypy bump2version build twine

docs:  ## Build HTML documentation using Sphinx
	sphinx-build -b html docs/ docs/_build/html
	@echo "Documentation built in docs/_build/html"

flushpip: SHELL := /bin/bash
flushpip:  ## Uninstall all packages from the current environment
	$(PIP) uninstall -y -r <($(PIP) freeze)

e: ## install this package into environment for development 
	$(PIP) install -e .

