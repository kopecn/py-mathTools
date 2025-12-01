# Contributing to py-mathTools

Thank you for considering contributing to this project — every bit helps, and all contributors are appreciated!

---

## How You Can Help

You can contribute in several ways:

### Report Bugs

Open an issue at [GitHub Issues](https://github.com/kopecn/pyMathTools/issues) with:

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

Follow these steps to set up `pyMathTools` locally:

1. **Fork** the repository:  
   [https://github.com/kopecn/pyMathTools/fork](https://github.com/kopecn/pyMathTools/fork)

2. **Clone** your fork:

    ```sh
    git clone git@github.com:your_name_here/pyMathTools.git
    cd pyMathTools
    ```

3. **Set up a virtual environment** and install the project locally:

    ```sh
    mkvirtualenv pyMathTools
    python setup.py develop
    ```

4. **Create a new branch**:

    ```sh
    git checkout -b your-feature-branch
    ```

5. **Run linters and tests**:

    ```sh
    make lint
    make test-all
    ```

6. **Commit and push your changes**:

    ```sh
    git add .
    git commit -m "Describe your changes"
    git push origin your-feature-branch
    ```

7. **Open a pull request.**

---

## PR Guidelines

Before submitting a pull request, make sure:

- [ ] Tests are included for new logic
- [ ] Documentation is updated if needed
- [ ] The project supports Python 3.12 and 3.13
- [ ] All tests pass (CI checks will run on PRs)

---

## Running Specific Tests

To run a targeted test suite:

```sh
pytest tests/test_pyMathTools.py
```


## Deploying (Maintainers Only)

1. Confirm all changes are committed (including `HISTORY.md`)
2. Bump the version:

```sh
bump2version patch  # Use major/minor/patch as needed
```

3. Push changes and tags:

```sh
git push
git push --tags
```

4. (Optional) Use [GitHub Actions](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python#publishing-to-pypi) to auto-deploy to PyPI.

## Code of Conduct
This project follows a [Contributor Code of Conduct](https://chatgpt.com/#:~:text=follows%20a%20Contributor-,Code,-of%20Conduct.%20By). By participating, you agree to uphold these standards.

Feel free to reach out or [open an issue](https://github.com/kopecn/pyMathTools/issues) with any questions.
