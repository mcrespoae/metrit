<div align="center">

<img src=".github/assets/banner.svg" alt="metrit: a dead simple resource monitoring decorator for Python" width="100%">

**A dead simple resource monitoring decorator for Python.**

[![PyPI version](https://img.shields.io/pypi/v/metrit?style=flat-square&label=PyPI&color=3775A9)](https://pypi.org/project/metrit/)
[![Python versions](https://img.shields.io/pypi/pyversions/metrit?style=flat-square&label=Python&color=3776AB)](https://pypi.org/project/metrit/)
[![License: MIT](https://img.shields.io/pypi/l/metrit?style=flat-square&color=green)](LICENSE)
[![Downloads per month](https://img.shields.io/pypi/dm/metrit?style=flat-square&label=Downloads%2Fmonth&color=orange)](https://pypi.org/project/metrit/)
[![Development status](https://img.shields.io/pypi/status/metrit?style=flat-square&color=blue)](https://pypi.org/project/metrit/)

[![Tests](https://github.com/mcrespoae/metrit/actions/workflows/push_to_main.yml/badge.svg)](https://github.com/mcrespoae/metrit/actions/workflows/push_to_main.yml)
[![Release](https://github.com/mcrespoae/metrit/actions/workflows/pypi_release.yml/badge.svg)](https://github.com/mcrespoae/metrit/actions/workflows/pypi_release.yml)
[![GitHub release](https://img.shields.io/github/v/release/mcrespoae/metrit?style=flat-square&color=blueviolet)](https://github.com/mcrespoae/metrit/releases)
[![Last commit](https://img.shields.io/github/last-commit/mcrespoae/metrit?style=flat-square)](https://github.com/mcrespoae/metrit/commits/main)
[![Open issues](https://img.shields.io/github/issues/mcrespoae/metrit?style=flat-square)](https://github.com/mcrespoae/metrit/issues)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/mcrespoae/metrit/pulls)

</div>

`metrit` is a Python package designed to simplify the process of measuring the execution resources of your functions through a straightforward decorator.

## Overview

The `metrit` decorator is a powerful tool for accurately measuring the execution resources of Python functions, including RAM, CPU, and I/O operations. It provides insights into resource utilization and potential bottlenecks. With features like automatic recursion detection and robust handling of process isolation and monitoring, `metrit` ensures precise measurements even for complex functions involving multiple processes.

## Installation

`metrit` requires Python 3.11 or newer.

You can install `metrit` using pip:

```bash
pip install metrit
```

## Usage

Utilizing the `metrit` decorator is simple and intuitive. Follow this section to learn how to make the most of its capabilities.

### Basic Usage

Below are some examples demonstrating `metrit`'s usage:

```python
from metrit import metrit

@metrit
def my_function():
    # Normal code of your function
    pass

my_function()
```

This will output something like:

```text
Function 'my_function'    27.14MB peak memory     0.00% avg of CPU     298B IO reads   2.44KB IO writes
```

### Advanced Usage

You can customize the behavior of the `metrit` decorator using various [Parameters](#parameters). Here is an example:

```python
from metrit import metrit
@metrit(verbose=True, find_children=True, isolate=True)
def my_function_with_args(a:int = 1, b:int = 2):
    return a + b

result = my_function_with_args(1, b=2)
```

This will provide detailed output:

```text
***** metrit data for function my_function_with_args: *****
	Args: (1,).
	Kwargs: {'b': 2}.
Maximum CPU usage: 0.00%.
Average CPU usage: 0.00%.
Peak memory usage: 0.08%.
Average memory usage: 0.08%.
Peak RSS memory usage: 27.14MB.
RSS memory growth: 172.00KB.
Average RSS memory usage: 27.14MB.
Peak VMS memory usage: 17.65MB.
VMS memory growth: 68.00KB.
Average VMS memory usage: 17.65MB.
IO read count: 5.
IO writes count: 2.
IO read bytes: 298B.
IO write bytes: 2.44KB.
***** End of metrit data. *****
```

More examples can be found in the [examples.py](https://github.com/mcrespoae/metrit/blob/main/examples/examples.py) script.

### Metrit in Production Environments

The `metrit` decorator is designed **exclusively for benchmarking and is not suitable for use in production code**. You can globally deactivate the `metrit` feature by setting the `MetritConfig.ACTIVE` flag to false at the top of your imports. While this will skip the decoration of callables, there may still be a minimal CPU overhead. For production-grade applications, it's recommended to manually remove the decorators and `metrit` imports to maintain optimal performance.

```python
from metrit import MetritConfig, metrit
MetritConfig.ACTIVE = False  # Deactivates the decorator
```

## Features

- Simplified usage.
- Accurate measurement of function resources.
- Ability to isolate the execution of the function for more accurate measurement.
- Support for functions, methods, `classmethod` and `staticmethod`.
- Human-readable data formatting.
- Optional verbose mode for detailed information.
- Ability to globally deactivate the `metrit` decorator.
- Optionally check the resources of child processes as well.
- Automatic recursion detection.
- Fully type-hinted (PEP 561 `py.typed`) for static analysis and editor support.

## Parameters

Using the decorator `@metrit` without any parameters executes the function once and displays the resources. However, you can enhance the experience using the following arguments:

- `find_children` (bool, optional): Specifies if the monitoring system should look for children processes as well. Defaults to False.
- `isolate` (bool, optional): Determines if the execution of the function is done in a separate process for more accurate results. See the [Isolate limitations](#isolate-limitations) for more details. Defaults to True.
- `verbose` (bool, optional): Controls whether detailed information is printed after execution. Defaults to False.

## Best Practices

The ideal way to use this package is by applying the decorator to the functions you want to measure and running them side by side to compare the results more easily.

- For more precise measurements, it is recommended to set `isolate` to `True`. Please see the [Isolate](#isolate) section to understand the limitations of this approach.

- Recursive functions should be encapsulated for better benchmarking. Please refer to the [Recursive functions](#recursive-functions) section to learn more.

- Decorating classes will return the class unmodified and will not be decorated. For more information about this decision, see the [Why is class decoration bypassed](#why-is-class-decoration-bypassed) in the [Limitations](#limitations) section.

## Recursive Functions

Measuring the resources of recursive functions using decorators can be challenging due to potential verbosity in the output. This package offers an automatic recursion detection feature, but it is still strongly recommended to [encapsulate the recursive function](#encapsulating-the-recursive-function) within another function for cleaner, more precise, and safer results. Recursive functions are supported with both `isolate = True` and `isolate = False`: recursion is detected per function and per thread, and isolated recursion reuses a single process instead of spawning one per recursion level.

### Using the Auto-Recursion Feature

The auto-recursion feature detects recursion in the decorated function by tracking whether the same function is already executing on the current thread (including inside an isolated process). If recursion is found, it will only output the measures taken to run the outermost call, plus a small overhead. It is not recommended to rely on this feature intentionally since the collected data might not be as accurate.

This feature is intended for passive use in case the user forgets to encapsulate the recursive function or for non-accurate comparisons.

```python
@metrit
def recursive_func(n):
    if n < 2:
        return n
    return recursive_func(n - 2) + recursive_func(n - 1)


# This will trigger the auto-recursion feature
result = recursive_func(3)
```

The result for this function could be something like:

```text
Function 'recursive_func'  27.14MB peak memory    54.46% avg of CPU   4.22KB IO reads   5.63KB IO writes
```

### Encapsulating the Recursive Function

The recommended option is to encapsulate the recursive function within another function and then, decorate and call the parent function. Here's an example:

```python
@metrit
def encapsulated_recursive_function(n):
    """A non-verbose wrapper for the recursive function."""
    def recursive_func(n):
        if n < 2:
            return n
        return recursive_func(n - 2) + recursive_func(n - 1)

    return recursive_func(n)

# Encapsulating the recursive function
result = encapsulated_recursive_function(3)
```

This approach enhances speed and measurement precision without incurring any performance penalties, even if `isolate = True`. However, it requires modifying your code to measure this type of function.

The result for this function could be something like:

```text
Function 'encapsulated_recursive_function'  27.14MB peak memory     0.00% avg of CPU     238B IO reads   2.01KB IO writes
```

Both examples are valid for comparisons between similar circumstances, but the latter is preferred.

## Isolate

The isolation feature works by encapsulating the decorated function in a separate process and then monitoring that process from another process to avoid interfering with the function's execution. If the isolation mechanism itself fails (for example, the isolated process crashes or cannot be started), `metrit` retries the function in the original process. Exceptions raised by the function itself are not an isolation failure: they are propagated to the caller without re-running the function.

## Limitations

While this package generally delivers excellent performance and reliability, it's essential to be aware of certain scenarios where using the `metrit` decorator could lead to unexpected behavior.

### Isolate Limitations

While the `isolate` feature is powerful and recommended for precise measurements, it can lead to unexpected results. Here are the main limitations:

- Using it in a non-wrapped recursive function will run the outermost call in an isolated process while the nested calls reuse that same process. Isolated recursion is supported, but measurements can still be less accurate than wrapping the recursive function explicitly. If any issues arise using this approach, feel free to open a GitHub issue.
- Methods are not affected by the `isolate` parameter and will be executed as if it were `False`. This is because encapsulating a method in a separate process from its object can lead to several issues. When methods are called, they rely on the state of the object they belong to. Isolating a method would require serializing (pickling) the entire object state and then deserializing it in a new process. This process can be complex and error-prone, leading to potential errors and inconsistencies. Therefore, to avoid these issues, `metrit` does not apply the isolate parameter to methods, ensuring they run in the same process as their object.

### Why is Class Decoration Bypassed?

When a class is decorated using `metrit`, it remains unmodified and is not decorated. If the user intends to measure the resources of `__init__` or any other constructor, it can be done directly on those methods.

This design decision was made due to a potential issue that arises when a decorated class is used in conjunction with spawning a new process. Specifically, if a class decorated with `metrit` is pickled for use in a separate process and then a method is called within that new process, it may result in a `PicklingError`.

### macOS Limitations

This package relies on the `psutil` package for retrieving data. Unfortunately, macOS and `psutil` do not support IO data per process, so IO data will not be shown on macOS.

### CPU Percentage Over 100

As noted in the psutil documentation:
> Note: the returned value can be > 100.0 in case of a process running multiple threads on different CPU cores.

Additionally, if `find_children` is set to `True`, the CPU percentage of all child processes will be added to the main process. This can easily result in the max and average CPU percentages exceeding 100%.

## Error Management and Warnings

### Errors

Exceptions raised by the decorated function are propagated to the caller in every mode (isolated, non-isolated and recursive). `metrit` only falls back to the main process when the isolation mechanism itself fails, so the function is never executed twice.

### Warnings

- Deprecation warnings will be added before removing a feature.

### Diagnostics and logging

Internal diagnostics (isolation failures, crashed helper processes, collection errors) are emitted
through the standard `logging` logger named `metrit` at `WARNING` level. A `NullHandler` is attached
by default, so the library stays silent unless you configure logging:

```python
import logging

logging.basicConfig(level=logging.INFO)  # or configure the "metrit" logger directly
```

The measured resource summary is still printed to stdout; it is not affected by logging config.

## How metrit works

Here's a detailed explanation of how `metrit` operates:

1. Function Process Execution:

    - If `isolate = True`, the decorated function runs in a separate process, referred to as the function process; otherwise it runs in the main process.
    - The process that is being measured is called the target process (the function process when isolated, otherwise the main process).

2. Baseline Snapshot:

    - Before the function runs, a short-lived helper process records a snapshot of the target process' current resources to use as a baseline.

3. Resource Monitoring:

    - Once the pooler signals it is ready, a pooling helper process (spawned as a child of the target process) samples its resources on a cadence that starts at 0.1 seconds and scales up to 5 seconds for longer-running functions.
    - CPU is sampled without blocking, so each sample covers the time since the previous one; per-tick values are summed across processes so the aggregate is coherent.
    - The helper process excludes itself from the samples, so the monitoring overhead is not counted.
    - This adaptive refresh rate minimizes the monitoring overhead for time-consuming functions.

4. Completion and Data Collection:

    - Upon completion, a signal stops the pooling process.
    - The pooled data is adjusted by subtracting the baseline snapshot to improve precision.
    - The final values are then printed.

5. Handling Failures and Parameters:

    - If the isolated process crashes (not a user exception), or if `isolate = False`, the function is executed in the main process with a fresh monitoring round. User exceptions are propagated as-is and the function is not re-executed.
    - The recursion checker tracks, per function and per thread, whether the same function is already executing (the isolated process seeds this state before running the function).
    - Methods are not isolated and will always run in the main process, as if `isolate` is `False`.

6. Child Process Monitoring:

    - When `find_children` is set to `True`, the library measures all processes spawned by the target process.
    - This feature is useful for nested functions or functions that spawn additional processes.

## How measurements are defined

- **CPU**: sampled as a percentage of a single CPU core and summed across the measured
  processes. It can exceed 100% (a process using several cores) and, with
  `find_children = True`, it is the sum of the target and its children sampled at the same
  instant.
- **Memory (RSS/VMS)**: the *peaks* are **absolute** values observed while the function ran;
  the *growth* is the peak minus the pre-run baseline (how much the function added). Averages
  are absolute means, and memory percentages are relative to the total system RAM. When
  measuring several processes, the totals are the sum across processes at each sample; note
  that summing RSS counts shared pages more than once, so it is an upper bound.
- **IO**: cumulative per-process counters read before and after the run, so the reported
  values are the bytes/counts performed during the run. Not available on macOS.
- **Output**: the one-line summary reports the single headline figure per metric — **peak
  memory**. The verbose output additionally shows RSS/VMS **growth** (peak minus baseline,
  i.e. what the function added) and mean values.
- **Sampling**: the target is sampled on a cadence that starts at 0.1s and grows up to 5s.
  Very short functions are dominated by sampling resolution and memory peaks shorter than the
  cadence can be missed; hold the state (e.g. keep the allocation alive) for stable numbers.

## Contributing

Contributions are welcome! Please follow these guidelines when contributing:

1. Fork the repository.
2. Install [uv](https://docs.astral.sh/uv/) and run `make install` to install all dependencies (backed by `uv sync`).
3. Create a new branch for your changes.
4. Implement your changes and commit them.
5. Push your changes to your forked repository.
6. Submit a pull request.

You can also open an issue if you find a bug or have a suggestion.

You can test your code using `make test` (current interpreter) or `make test-all` (all supported Python versions), and `make example` to trigger the examples. You can also run `make check` to lint (`flake8`) and type-check (`basedpyright`). Please, check the [Makefile](https://github.com/mcrespoae/metrit/blob/main/Makefile) to know more about commands.

## Testing

The package has been thoroughly tested using unittesting. Test cases can be found in the [tests folder](https://github.com/mcrespoae/metrit/tree/main/tests).

CI runs the suite across Python 3.11–3.14 on Linux, macOS and Windows, and reports code coverage.

## License

This project is licensed under the [MIT License](https://github.com/mcrespoae/metrit/blob/main/LICENSE).

## Contributors

- [Mario Crespo](https://github.com/mcrespoae)
