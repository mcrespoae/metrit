# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-13

### Added

- PEP 561 `py.typed` marker so the type hints are visible to static analysis and editors.
- `metrit.__version__` attribute, read from the installed package metadata.
- `make lint`, `make typecheck`, `make check`, `make test-all` and `make test-accuracy` targets.
- `basedpyright` type checking (config + CI) and a `.flake8` configuration.
- Opt-in accuracy checks (`tests/accuracy_checks.py`) validating memory growth, CPU, IO and
  child-process measurement against known workloads.
- Regression tests for isolation errors, hard crashes, recursion, monitoring
  formatting/graceful degradation and method-argument extraction.

### Changed

- **Measurement model**: memory now reports absolute peak RSS/VMS plus growth over the
  pre-run baseline (the previous values were baseline-subtracted deltas); memory percentages
  are absolute peaks; the concise output reports *peak memory*.
- **Coherent aggregation**: the target and its children are sampled in a single pass and their
  per-tick values are summed, so CPU/memory totals come from the same time windows instead of
  summing per-process averages taken at different times.
- **Non-blocking sampling**: CPU is read on cached `psutil.Process` objects (`interval=None`),
  removing the second sleep and giving each sample a well-defined window. The pooler now
  signals readiness before the function starts, so short functions are actually measured.
- Diagnostic messages are emitted through the standard `logging` logger named `metrit`
  (silent by default) instead of `print`; the resource summary is still printed to stdout.
- CI runs lint, type checking and tests across Linux, macOS and Windows and Python 3.11–3.14,
  reports code coverage, and its path filters cover tests, examples, workflow and config.
- README presentation (banner + badges), a "How measurements are defined" section and
  documentation accuracy fixes.

### Fixed

- Isolated calls could hang forever when the function process died hard (segfault,
  `os._exit`, `SIGKILL`); queue reads are now bounded and detect crashes.
- User exceptions in `isolate=True` mode were caught as isolation crashes and executed the
  function twice; user errors now propagate without re-running.
- Recursion state was left behind after an exception, which made every later call of a
  decorated function be misdetected as recursive.
- Recursion detection relied on a global queue that was not thread-safe and silently failed
  under the spawn start method (Windows/macOS); it is now per-function and per-thread.
- Failed CPU/RAM/IO samples were recorded as zeros, biasing the averages and overwriting
  previously collected IO counters.
- The pooler could fail to measure short functions because it started sampling after they
  finished; a readiness handshake and a final IO refresh fix the race.
- PyPI publishing was triggered by any tag; it is now limited to version tags.

[Unreleased]: https://github.com/mcrespoae/metrit/compare/1.0.0...HEAD
[1.0.0]: https://github.com/mcrespoae/metrit/releases/tag/1.0.0
