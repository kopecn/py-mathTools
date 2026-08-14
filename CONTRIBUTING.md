# Contributing to py-MathTools

Thank you for considering contributing to this project — every bit helps, and all contributors are appreciated!

---

## How You Can Help

You can contribute in several ways:

### Report Bugs

Open an issue at [GitHub Issues](https://github.com/kopecn/py_math_tools/issues) with:

- Your operating system and version
- Any relevant local setup details
- Clear steps to reproduce the issue

### Fix Bugs

Look for issues tagged with `bug` and `help wanted`.

### Implement Features

Check issues tagged with `enhancement` and `help wanted`.

### Improve Documentation

Contribute to docstrings, the official docs, or share tutorials and blog posts.

### Submit Feedback or Ideas

For new features, please:

- Explain how the feature should work
- Keep the scope focused
- Be mindful that this is a volunteer-driven project

---

## Getting Started

Follow these steps to set up `py_math_tools` locally:

1. **Fork** the repository:  
   [https://github.com/kopecn/py_math_tools/fork](https://github.com/kopecn/py_math_tools/fork)

2. **Clone** your fork:

    ```sh
    git clone git@github.com:your_name_here/py_math_tools.git
    cd py_math_tools
    ```

3. **Set up the environment** and install the project with dev dependencies:

    ```sh
    make dev          # uv: create .venv + install -e ".[dev]" from pyproject
    # (or `make installDev` for the pip fallback)
    ```

4. **Create a new branch**:

    ```sh
    git checkout -b your-feature-branch
    ```

5. **Run linters, type checks, and tests**:

    ```sh
    make uv-fullCheck     # ruff + mypy + pytest
    # or individually: make uv-lint · make uv-typecheck · make uv-test
    ```

6. **Commit and push your changes**:

    ```sh
    git add .
    git commit -m "Describe your changes"
    git push origin your-feature-branch
    ```

7. **Open a pull request.**

---

## Co-developing with sibling repositories

When you need to develop this project against a **local, unreleased** checkout of a sibling
library (e.g. it lives at `../my-sibling-lib`), use a **`requirements-local.txt`** overlay. Local
and git/path resolution never goes in `pyproject.toml` — the manifest stays dependency **names
only** (putting path/git pointers there is a module-deployment hazard).

```sh
echo "-e ../my-sibling-lib" >> requirements-local.txt
make uv-sync-local     # creates the venv, installs -r requirements-local.txt, then -e ".[dev]"
```

`requirements-local.txt` is **gitignored** and never read by CI/release, so a solo checkout is
unaffected (just don't create the file).

---

## PR Guidelines

Before submitting a pull request, make sure:

- [ ] Tests are included for new logic
- [ ] Documentation is updated if needed
- [ ] The project supports Python 3.10 through 3.13
- [ ] All tests pass (CI checks will run on PRs)

---

## Running Specific Tests

To run a targeted test suite:

```sh
pytest tests/test_py_math_tools.py
```


## Changelog (`HISTORY.md`)

This project keeps a human-readable changelog in `HISTORY.md`, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The best-known method:

1. **Every PR that changes behavior** adds a bullet under the `## [Unreleased]`
   section, in the appropriate group: `Added`, `Changed`, `Deprecated`, `Removed`,
   `Fixed`, or `Security`. No "internal-only" changes (refactors, CI) need an entry
   unless they affect users.
2. **At release time** (maintainers), rename `## [Unreleased]` to the new version and
   date, e.g. `## [1.2.0] - 2025-08-16`, then add a fresh empty `## [Unreleased]`
   block above it and update the comparison links at the bottom.
3. Keep entries imperative and user-facing ("Add X", "Fix Y"), not commit-message dumps.

## Deploying (Maintainers Only)

1. Update `HISTORY.md`: roll `[Unreleased]` into the new version + date (see above).
2. Confirm all changes are committed (including `HISTORY.md`).
3. Bump the version:

```sh
bump2version patch  # Use major/minor/patch as needed
```

4. Push changes and tags:

```sh
git push
git push --tags
```

5. (Optional) Use [GitHub Actions](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python#publishing-to-pypi) to auto-deploy to PyPI.

## Code of Conduct
This project follows a [Contributor Code of Conduct](https://chatgpt.com/#:~:text=follows%20a%20Contributor-,Code,-of%20Conduct.%20By). By participating, you agree to uphold these standards.

Feel free to reach out or [open an issue](https://github.com/kopecn/py_math_tools/issues) with any questions.
