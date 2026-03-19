# Extension Testing Framework Design

This document describes the design for testing Metaflow extensions within the existing QA test suite, addressing the questions raised in [Issue #8](https://github.com/Netflix/metaflow/issues/8).

## 1. CLI / Configuration Interface

### `run_tests.py` Options

Two new CLI options are added to `test/core/run_tests.py`:

```
--extension PATH    Path to an extension directory to include in test runs.
                    Can be specified multiple times.

--include-extension-tests
                    Also discover and run tests provided by extensions
                    (from metaflow_extensions/<org>/core_tests/tests/).
```

**Usage examples:**

```bash
# Run core tests with a single extension loaded
python run_tests.py --extension ../../test/extensions/packages/sample_ext

# Run core tests + extension-provided tests
python run_tests.py --extension ../../test/extensions/packages/sample_ext \
    --include-extension-tests

# Multiple extensions
python run_tests.py --extension ./ext_a --extension ./ext_b

# Combine with existing filters
python run_tests.py --extension ./ext_a --tests SampleExtDecoratorTest \
    --contexts python3-all-local --debug
```

### `test_runner` Integration

The `test_runner` shell script passes `--extension` flags through to `run_tests.py`. For extensions that are pip-installable (contain `setup.py` or `pyproject.toml`), the script runs `pip install -e <path>` before invoking `run_tests.py`.

```bash
./test_runner --extension test/extensions/packages/sample_ext
```

### tox Integration

tox passes all extra arguments to `test_runner` via `{posargs}`:

```bash
tox -e local -- --extension test/extensions/packages/sample_ext --include-extension-tests
```

## 2. Dynamic Installation Mechanism

Extensions are loaded into test subprocesses through two paths:

### Path A: PYTHONPATH (directory-based extensions)

When `--extension /path/to/ext` is specified, the path is added to `PYTHONPATH` in every test subprocess's environment. The extension's `metaflow_extensions/<org>/` namespace package is then discovered automatically by `extension_support/__init__.py` via its PYTHONPATH scan (the `_get_extension_packages()` function, PYTHONPATH branch at ~line 828).

This is the same mechanism already used by `test/core/metaflow_extensions/test_org/`, which is loaded by prepending `test/core/` to `PYTHONPATH` at line 204 of `run_tests.py`.

### Path B: pip install (packaged extensions)

When `test_runner` detects `setup.py` or `pyproject.toml` in the extension directory, it runs `pip install -e <path>` before starting tests. The extension is then discovered via the installed-distribution path in `_get_extension_packages()` (~line 665).

Both paths coexist: a pip-installed extension is also discoverable via PYTHONPATH, but the distribution path takes precedence in the discovery order.

## 3. Extension Test Discovery Convention

Extensions can provide tests at two tiers:

### Tier 1: Integration tests (`core_tests/tests/`)

Location: `metaflow_extensions/<org>/core_tests/tests/*.py`

These files contain `MetaflowTest` subclasses compatible with the `run_tests.py` harness. They are discovered by the modified `iter_tests()` function when `--include-extension-tests` is specified.

The discovery mechanism:
1. For each `--extension` path, scan `metaflow_extensions/<org>/core_tests/tests/`
2. Import each `.py` file and find all `MetaflowTest` subclasses
3. Merge them into the test list alongside core tests
4. Run them through the same graph × context × executor matrix

Example: `metaflow_extensions/sample_ext/core_tests/tests/sample_ext_test.py`

### Tier 2: Unit tests (`tests/`)

Location: `metaflow_extensions/<org>/tests/*.py`

Standard pytest tests. These are run as a separate step:

```bash
pytest test/extensions/packages/sample_ext/metaflow_extensions/sample_ext/tests/
```

These test extension internals in isolation (no flow execution needed).

## 4. Backend × Extension Matrix Strategy

### Current matrix

The existing test matrix is: `tests × graphs × contexts × executors`.

Adding extensions creates: `tests × graphs × contexts × executors × extensions`.

### Avoiding combinatorial explosion

Rather than generating all combinations, the framework uses **selective composition**:

1. **Core tests + extension loaded**: Run the existing core test suite with an extension's PYTHONPATH injected. This verifies the extension doesn't break core functionality. No new test cases needed.

2. **Extension-provided tests**: Only run when `--include-extension-tests` is set. These tests define their own `SKIP_GRAPHS` and context compatibility, so irrelevant combinations are pruned automatically.

3. **Context overlays** (future): Extensions can provide `core_tests/contexts.json` with additional contexts or overrides. For example, an extension providing an Argo backend would define a context with `"top_options": ["--with", "argo-workflows"]`. This is not yet implemented but the architecture supports it.

### CI matrix

In GitHub Actions or tox, the matrix is defined explicitly:

```yaml
strategy:
  matrix:
    extension: [sample_ext, other_ext]
steps:
  - run: |
      cd test/core
      PYTHONPATH=../../ python run_tests.py \
        --extension ../../test/extensions/packages/${{ matrix.extension }} \
        --include-extension-tests
```

For multi-extension testing, add a separate matrix entry:

```yaml
    extension: [sample_ext, other_ext, "sample_ext+other_ext"]
```

## 5. Isolation Guarantees

### Subprocess isolation

Each test flow runs in a subprocess with a clean environment constructed in `run_test()`. Extension directories are injected into the subprocess's `PYTHONPATH`, so they are only visible to that subprocess. The parent `run_tests.py` process does not load extension code at runtime (only during test discovery in `iter_tests()`).

### `METAFLOW_EXTENSIONS_SEARCH_DIRS`

The `METAFLOW_EXTENSIONS_SEARCH_DIRS` environment variable (read in `extension_support/__init__.py`) restricts extension discovery to specific directories. When set, both the distribution path and PYTHONPATH path in `_get_extension_packages()` filter results to only extensions rooted in those directories.

This can be used for strict isolation:

```bash
# Only load sample_ext, ignore any other installed extensions
METAFLOW_EXTENSIONS_SEARCH_DIRS=/path/to/sample_ext python run_tests.py ...
```

The current implementation does **not** set this automatically — all discoverable extensions are loaded. This is intentional: the default behavior should match production (where all installed extensions are active). Strict isolation is opt-in.

### tox factor isolation

For CI, tox factors provide virtualenv-level isolation:

```ini
[testenv:local-ext_a]
commands = ./test_runner --extension test/extensions/packages/ext_a

[testenv:local-ext_b]
commands = ./test_runner --extension test/extensions/packages/ext_b
```

Each factor creates a separate virtualenv, so pip-installed extensions in one factor don't affect another.

### Known pitfalls

1. **Module name collisions**: If two extensions provide test files with the same name in `core_tests/tests/`, `importlib.import_module` may return a cached module. Extension test files should use unique, prefixed names (e.g., `sample_ext_test.py`).

2. **Import-time side effects**: Extensions that modify global state at import time (e.g., monkey-patching) may affect the `run_tests.py` process itself during `iter_tests()` discovery. The mitigation is that `iter_tests()` only imports test files, not extension code — the extension itself is loaded in subprocesses.

3. **PYTHONPATH ordering**: Multiple `--extension` flags prepend paths in order. If two extensions override the same module, the last `--extension` wins (leftmost in PYTHONPATH). This matches the documented deterministic load order.

## 6. Prototype: Sample Extension

The `test/extensions/packages/sample_ext/` directory is a complete, working prototype demonstrating:

- **Extension structure**: `metaflow_extensions/sample_ext/` with plugins, config, and promoted submodules
- **Step decorator**: `SampleStepDecorator` that sets an artifact on each step
- **Config value**: `METAFLOW_SAMPLE_EXT_VALUE = 99`
- **Promoted module**: `sample_module` with `sample_value = 99`
- **Integration test**: `core_tests/tests/sample_ext_test.py` — a `MetaflowTest` subclass verifying all three mechanisms
- **Unit tests**: `tests/test_sample_ext_unit.py` — pytest tests for extension internals

### Running the prototype

```bash
# Core tests with sample_ext loaded (verify no breakage)
cd test/core
PYTHONPATH=../../ python run_tests.py \
    --extension ../../test/extensions/packages/sample_ext \
    --contexts python3-all-local --debug

# Core tests + extension-provided integration test
PYTHONPATH=../../ python run_tests.py \
    --extension ../../test/extensions/packages/sample_ext \
    --include-extension-tests \
    --tests SampleExtDecoratorTest \
    --contexts python3-all-local --debug

# Extension unit tests
pytest test/extensions/packages/sample_ext/metaflow_extensions/sample_ext/tests/
```

## Files Changed

| File | Change |
|------|--------|
| `test/core/run_tests.py` | Added `--extension` and `--include-extension-tests` CLI options; extended `iter_tests()` for multi-root discovery; added ext PYTHONPATH to subprocess env |
| `test_runner` | Added `install_user_extensions()` for pip-installing packaged extensions; passes `$@` through to `run_tests.py` |
| `test/extensions/packages/sample_ext/` | New prototype extension with decorator, config, promoted module, integration test, and unit tests |
| `test/extensions/DESIGN.md` | This document |
