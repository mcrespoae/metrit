# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- PEP 561 `py.typed` marker so the type hints are visible to static analysis and editors.
- `metrit.__version__` attribute, read from the installed package metadata.
- `make lint`, `make typecheck`, `make check` and `make test-all` targets.
- `basedpyright` type checking (config + CI) and a `.flake8` configuration.
- Regression tests for isolation errors, hard crashes, recursion, monitoring
  formatting/graceful degradation and method-argument extraction.

### Changed

- Diagnostic messages are emitted through the standard `logging` logger named `metrit`
  (silent by default) instead of `print`; the resource summary is still printed to stdout.
- CI now runs lint, type checking and tests across Linux, macOS and Windows and Python
  3.11–3.14, and reports code coverage.
- CI path filters now cover tests, examples, workflow and configuration changes.
- README presentation (banner + badges) and documentation accuracy.

### Fixed

- Isolated calls could hang forever when the function process died hard (segfault,
  `os._exit`, `SIGKILL`); queue reads are now bounded and detect crashes.
- User exceptions in `isolate=True` mode were caught as isolation crashes and executed
  the function twice; user errors now propagate without re-running.
- Recursion state was left behind after an exception, which made every later call of a
  decorated function be misdetected as recursive.
- Recursion detection relied on a global queue that was not thread-safe and silently
  failed under the spawn start method (Windows/macOS); it is now per-function and
  per-thread.
- Failed CPU/RAM/IO samples were recorded as zeros, biasing the averages and overwriting
  previously collected IO counters.
- PyPI publishing was triggered by any tag; it is now limited to version tags.

[Unreleased]: https://github.com/mcrespoae/metrit/compare/0.1.6...HEAD
