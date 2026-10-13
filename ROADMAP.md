# metrit — Review, Bug Fixes & Roadmap

This document tracks the findings from a full review of the package (source, tests,
examples, CI, packaging) and the remediation plan. **P0 is implemented; P1–P4 are
pending.**

Severity: **C** = critical, **H** = high, **M** = medium, **L** = low/hygiene.

## Findings

| ID | Sev | Location | Description / Impact | Phase |
|----|-----|----------|----------------------|-------|
| H1 | C/H | `core.py` (`isolate_function`), `Monitoring.py` (`take_snapshot`, `stop_monitoring`, `pool_stats`) | Blocking `Queue.get()` with no timeout hung the caller forever when a helper/isolated process died hard (segfault, `os._exit`, `SIGKILL`, `SystemExit`). Also, joining before draining could deadlock on large payloads, and orphaned monitor processes could linger. | **P0 (done)** |
| H2 | C/H | `core.py` (`metrit_wrapper`, `isolate_function`, `call_func_isolated`) | In `isolate=True` mode any user exception was caught as an "isolation crash" and the function was **executed twice** (side effects duplicated). | **P0 (done)** |
| H3 | H | `core.py` (`metrit_wrapper`, `handle_recursive_call`) | `called_func_stack` was only popped on success; after an exception every later call was misdetected as recursive and metrics were never printed again. | **P0 (done)** |
| H4 | H | `core.py`, `utils.py` | Recursion state was one global `Queue` shared by all decorated functions and is not thread-safe; on spawn platforms (Windows/macOS) the child re-imported the module and created its own queue, so isolated-recursion detection silently did nothing. | **P1 (done)** |
| M1 | M | `StatCollector.py` | Dead/confusing `except` block in `collect_io_counters`: the inner `if` always fell through to an unconditional `continue`. Removed; vanished children are now skipped cleanly. Previously-collected samples for a dead child are intentionally kept (they are valid data). | **P2 (done)** |
| M2 | M | `StatCollector.py` | `get_current_stats`/`get_io_counters` swallowed all errors and returned zeros; the zeros polluted averages and silently overwrote valid counters. They now return `None` and callers skip the sample, so failed reads no longer bias results. | **P2 (done)** |
| M3 | M | `StatCollector.py` | With `find_children=True` only the pooling process was excluded on paper. Verified empirically (child enumeration showed the helper + user child; reported memory only reflected the user child) that self-exclusion plus baseline subtraction already handle it. Added a regression unit test. | **P2 (done)** |
| M4 | M | `utils.py` | `check_is_recursive_func` could append `func` twice while callers popped once → unbounded stack growth for deep isolated recursion. | **P1 (done)** |
| M5 | M | `core.py` (`isolate_function`) | `except` referenced `func_process` which may be unbound if `Process(...)`/`start()` fails, masking the real error. | P0 (done) |
| M6 | M | `core.py`, `Monitoring.py`, `StatCollector.py` | Diagnostic messages used `print` unconditionally. Now emitted through the `metrit` logger (`WARNING`) with a `NullHandler` by default; the metrics summary still prints to stdout. | **P3 (done)** |
| L1 | L | `.github/workflows/push_to_main.yml:9-12` | Path filters are `metrit/**.py` only, so test-only / config-only PRs skip CI. | P4 |
| L2 | L | `.github/workflows/push_to_main.yml` | Lint was a near no-op (`--max-line-length=350`, blanket ignores). Now `.flake8` (max 120, no blanket ignores), tightened CI, and a `basedpyright` type-check step. | **P3 (done)** |
| L3 | L | `.github/workflows/pypi_release.yml:5-6` | Publishes on **any** tag (`'*'`); an accidental tag triggers a PyPI upload. | P4 |
| L4 | L | `tests/` | Removed the orphan `test_monitoring*.pyc`; added `tests/test_monitoring.py` (crash detection, print formatting, graceful degradation) and `extract_callable_and_args_if_method` tests. | **P3 (done)** |
| L5 | L | `README.md` | "How metrit works" described a peer monitor process created before the function; rewritten to match the implementation (baseline snapshot + pooling helper as a child of the target process). | **P2 (done)** |
| L6 | L | `tests/test_metrit.py`, `examples/examples.py` | Temp file is now removed in a `finally`; `examples.py` CPU loop reduced from ~100M to 5M iterations. | **P3 (done)** |
| L7 | L | `pyproject.toml`, `Makefile` | Added `[tool.pyright]` + `basedpyright` dev dep, `.flake8`, and `make lint/typecheck/check` (also wires the previously-missing `check` target used by the upload rules). | **P3 (done)** |

## Remediation plan

| Phase | Items | Deliverable | Roles | Estimate | Status |
|-------|-------|-------------|-------|----------|--------|
| **P0 — Stop the bleeding** | H1, H2, H3, M5 | Drain result queue while polling process liveness; timeouts + liveness checks on monitor waits; distinguish user error from isolation crash (tagged report, `IsolationError`); `try/finally` stack balance; monitor exits if the monitored pid is gone. New tests: raising function executed once, hard crash recovery, no stack leak. | 1 senior Python eng | 3–5 days | **Done** |
| **P1 — Recursion correctness** | H4, M4 | Replaced the global queue with per-function, per-thread `RecursionState` (in `utils.py`) keyed by a process-independent `function_key` (module normalized for `__mp_main__`, raw `co_code` bytes). The isolated child seeds its own state via the key, so recursion is detected on fork **and** spawn without spawning a process per level. New tests: `tests/test_recursion.py`. | 1 senior eng (+ reviewer) | 5–8 days | **Done** |
| **P2 — Measurement accuracy** | M1, M2, M3, L5 | Removed dead collector code; failed samples return `None` and are skipped (no zero bias, no counter overwrite); confirmed helper exclusion + added regression test; rewrote the "How metrit works" docs. New tests in `tests/test_StatsCollector.py`. | 1 mid eng | 3–4 days | **Done** |
| **P3 — Observability & hygiene** | M6, L2, L4, L6, L7 | Diagnostics via `logging` (NullHandler default); `.flake8` + `basedpyright` config and CI step; `make lint/typecheck/check`; new `test_monitoring.py` + utils tests; fixed stale bytecode, temp-file cleanup, faster examples. | 1 mid eng | 2–3 days | **Done** |
| **P4 — CI/CD hardening** | L1, L3 | Include tests/config in path filters; pin release tags (e.g. `v*.*.*`); add formatter/type-check job. | 1 devops/mid eng | 1 day | Pending |

**Total:** ~2.5–4 engineer-weeks for one engineer, or ~2 weeks with two engineers.
P0 was the highest-ROI slice and is complete.

## Notes

- Platform policy: **all platforms are first-class** (Linux fork and Windows/macOS spawn).
- The stale `FEA-AutomaticRecursionIsolation` branch was removed: its `core.py`/`utils.py`
  are byte-identical to `main` (the feature already shipped) and it reverted the `uv`
  migration plus a monitoring fix.
