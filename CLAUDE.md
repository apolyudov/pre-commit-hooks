# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A collection of [pre-commit](http://pre-commit.com) hooks for git. Provides 6 hooks: `forbid-crlf`, `remove-crlf`, `forbid-tabs`, `remove-tabs`, `chmod`, and `insert-license`. Published as a pip-installable package. Requires `pre-commit` >= 3.2.0 and Python >= 3.7.

## Common Commands

All Python tooling (pytest, pip, etc.) must run inside a virtual environment. If `.venv/` does not exist, create it first:

```shell
# Create and activate the virtual environment
python3 -m venv .venv
# Then use .venv/bin/<tool> directly, e.g.:
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -vv
```

```shell
# Install in development mode with all dev dependencies
.venv/bin/pip install -r requirements-dev.txt

# Run all tests with coverage
.venv/bin/pytest -vv

# Run a single test file
.venv/bin/pytest tests/insert_license_test.py

# Run a specific test by name
.venv/bin/pytest tests/insert_license_test.py::test_license_insertion_python

# Run all pre-commit hooks (lint, type-check, test, format check)
pre-commit run --all-files --verbose

# Lint only
.venv/bin/pylint pre_commit_hooks/

# Type-check only
.venv/bin/mypy pre_commit_hooks/ --ignore-missing-imports --check-untyped-defs --show-error-codes
```

## Architecture

**Hook modules** (`pre_commit_hooks/`): Each hook is a standalone Python script with a `main(argv=None)` entry point. Simple hooks (`forbid_crlf`, `remove_crlf`, `forbid_tabs`, `remove_tabs`, `chmod`) are single-file ~40-60 line scripts that read files in binary mode and process them. `insert_license` is the most complex hook at ~700 lines.

**Hook registration**: Hooks are declared in `.pre-commit-hooks.yaml` (entry, language, file types, stages). The `setup.py` `console_scripts` entry points map CLI command names to `module:main` functions.

**insert_license architecture**: This hook handles license header detection, insertion, removal, and fuzzy matching. Key concepts:
- `LicenseInfo` namedtuple carries comment style config + prefixed/plain license text
- Comment styles use pipe-delimited triplets: `<start>|<prefix>|<end>` (e.g., `/*| *| */`)
- License matching is exact by default; optional fuzzy matching uses `rapidfuzz.fuzz.token_set_ratio`
- Year range handling via `--use-current-year` updates copyright ranges in headers
- Files are read with fallback encoding: UTF-8 first, then ISO-8859-1

**Tests** (`tests/`): Tests use `pytest` with `@pytest.mark.parametrize` for data-driven testing. The `tests/utils.py` module provides `chdir_to_test_resources()` (context manager that changes into `tests/resources/`) and `capture_stdout()`. Test resource files in `tests/resources/` are named descriptively (e.g., `module_with_license.py`, `module_without_license.py`) and serve as both input and expected output fixtures.

## Coding Conventions

- Formatted with `black` (excludes `tests/resources/`)
- Python 3.7+ syntax (`from __future__ import annotations` used in `insert_license`)
- Max line length: 150 (configured in `.pylintrc`)
- Hooks accept `argv=None` for testability, called via `main(sys.argv[1:])` from `__main__`
- Return codes: 0 = success, 1 = files modified/commit should be aborted, 2 = configuration error

## Release Process

1. Bump version in `README.md`, `setup.py`, and `.pre-commit-config.yaml`
2. `git commit -am "New release $version" && git tag $version && git push && git push --tags`
3. Publish a GitHub release
