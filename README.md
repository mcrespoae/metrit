
# metrit

![PyPI](https://img.shields.io/pypi/v/metrit?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/metrit)

## Overview

`metrit` is a Python package designed to simplify the process of measuring the execution resources of your functions through a straightforward decorator.

## Installation

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
Function 'my_function'    24.00KB avg of memory     0.00% avg of CPU     239B IO reads   2.05KB IO writes.
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
    Average memory usage: 0.00%.
    Maximum RSS memory usage: 112.00KB.
    Average RSS memory usage: 112.00KB.
    Maximum VMS memory usage: 68.00KB.
    Average VMS memory usage: 68.00KB.
    IO read count: 5.
    IO writes count: 2.
    IO read bytes: 239B.
    IO write bytes: 2.01KB.
***** End of metrit data. *****
```

More examples can be found in the [examples.py](https://github.com/mcrespoae/metrit/blob/main/examples/examples.py) script.

### Metrit in Production Environments

The `metrit` decorator is designed **exclusively for benchmarking and is not suitable for use in production code**. You can globally deactivate the `metrit` feature by setting the `MetrittConfig.ACTIVE` flag to false at the top of your imports. While this will skip the decoration of callables, there may still be a minimal CPU overhead. For production-grade applications, it's recommended to manually remove the decorators and `metrit` imports to maintain optimal performance.

```python
from metrit import MetritConfig, metrit
MetritConfig.ACTIVE = False  # Deactivates the decorator
```

## Features

- Simplified usage.
- Accurate measurement of function resources.
- Ability to isolate the execution of the function for more accurate measurement.
- Support for functions, methods, `classmethod` and `staticmethods`.
- Human-readable data formatting.
- Optional verbose mode for detailed information.
- Ability to globally deactivate the `metrit` decorator.
- Optional check children processes' resources as well.
- Automatic recursion detection.

## Parameters

Using the decorator `@metrit` without any parameters executes the function once and displays the resources. However, you can enhance the experience using the following arguments:

- `find_children` (bool, optional): Specifies if the monitoring system should look for children processes as well. Defaults to False.
- `isolate` (bool, optional): Determines if the execution of the function is done in a separate process for more accurate results. See the [Isolate limitations](#isolate-limitations) for more details. Defaults to False.
- `verbose` (bool, optional): Controls whether detailed information is printed after execution. Defaults to False.

## Best Practices

The ideal way to use this package is by applying the decorator to the functions you want to measure and running them side by side to compare the results more easily.

- For more precise measurements, it is recommended to set `isolate` to `True`. Please see the [Isolate](#isolate) section to understand the limitations of this approach.

- Recursive functions should be encapsulated for better benchmarking. Please refer to the [Recursive functions](#recursive-functions) section to to learn more.

- Decorating classes will return the class unmodified and will not be decorated. For more information about this decision, see the [Why is class decoration bypassed](#why-is-class-decoration-bypassed) in the [Limitations](#limitations) section.

## Recursive Functions

Measuring the resources of recursive functions using decorators can be challenging due to potential verbosity in the output. This package offers an automatic recursion detection feature, but it is strongly recommended [encapsulating the recursive function](#encapsulating-the-recursive-function) within another function for cleaner, more precise, and safer results. Using recursive functions with `isolate = True` will not trigger the automatic recursion checker, making bad measurements, slowing time and making a too verbose output.

### Using the Auto-Recursion Feature

The auto-recursion feature detects recursion in the decorated function by checking the parent call function. If recursion is found, it will only output the measures taken to run the appropriate function, plus a small overhead. It is not recommended to rely on this feature intentionally since the collected data might not be as accurate.

This feature is intended for passive use in case the user forgets to encapsulate the recursive function or for non-accurate comparisons.

```python
@metrit
def recursive_func(n):
    if n == 0:
        return 0
    else:
        return n + recursive_func(n - 1)


# This will trigger the auto-recursion feature
result = recursive_func(3)
```

### Encapsulating the Recursive Function

The recommended option is to encapsulate the recursive function within another function and then, decorate and call the parent function. Here's an example:

```python
@metrit
def encapsulated_recursive_function(n):
    """A non-verbose wrapper for the recursive function."""
    def recursive_func(n):
        if n == 0:
            return 0
        else:
            return n + recursive_func(n - 1)

    return recursive_func(n)

# Encapsulating the recursive function
result = encapsulated_recursive_function(3)
```

This approach enhances readability without incurring any performance penalties, even if `isolate = True`. However, it requires modifying your code to measure this type of function.

## Isolate

The isolation feature works by encapsulating the decorated function in a separate process and then monitoring that process from another process to avoid interfering with the function's execution. If any part of this process fails, `metrit` will retry running the function in the original process.

## Limitations

While this package generally delivers excellent performance and reliability, it's essential to be aware of certain scenarios where using the `metrit` decorator could lead to unexpected behavior.

### Isolate Limitations

While the `isolate` feature is powerful and recommended for precise measurements, it can lead to unexpected results. Here are the main limitations:

- Using it in a non-wrapped recursive function will generate a process for each recursive call, wasting resources, performing inaccurate measurements, and generating verbose output. Ensure you are not using it directly with a recursive function.
- Methods are not affected by the `isolate` parameter and will be executed as if it were `False`. This is because encapsulating a method in a separate process from its object can lead to issues. When methods are called, they rely on the state of the object they belong to. Isolating a method would require serializing (pickling) the entire object state and then deserializing it in a new process. This process can be complex and error-prone, leading to potential errors and inconsistencies. Therefore, to avoid these issues, `metrit` does not apply the isolate parameter to methods, ensuring they run in the same process as their object.

### Why is Class Decoration Bypassed?

When a class is decorated using `metrit`, it remains unmodified and is not decorated. If the user intends to measure the time of `__init__` or any other constructor, it can be done directly on those methods.

This design decision was made due to a potential issue that arises when a decorated class is used in conjunction with spawning a new process. Specifically, if a class decorated with `metrit` is pickled for use in a separate process and then a method is called within that new process, it may result in a `PicklingError`.

### MacOs Limitations

This package relies on the `psutil` package for retrieving data. Unfortunately, macOS and `psutil` do not support IO data per process, so IO data will not be shown on macOS.

### CPU Percentage Over 100

As noted in the psutil documentation:
> Note: the returned value can be > 100.0 in case of a process running multiple threads on different CPU cores.

Additionally, if `find_children` is set to `True`, the CPU percentage of all child processes will be added to the main process. This can easily result in the max and average CPU percentages exceeding 100%.

## Error Management and Warnings

### Errors

If an error occurs while executing the decorated function in non-isolated mode or within a recursively decorated function, the error will be propagated to the user's function.

### Warnings

- Deprecation warnings will be added before removing a feature.
- If recursion is detected, a warning will be prompted. In such cases, refer to the [Recursive functions](#recursive-functions) section.

## Contributing

Contributions are welcome! Please follow these guidelines when contributing:

1. Fork the repository.
2. Use `make install` to install all dependencies.
3. Create a new branch for your changes.
4. Implement your changes and commit them.
5. Push your changes to your forked repository.
6. Submit a pull request.

You can also open an issue if you find a bug or have a suggestion.

You can test your code using `make test` and `make example` to trigger the examples. Please, check the [Makefile](https://github.com/mcrespoae/metrit/blob/main/Makefile) to know more about commands.

## Testing

The package has been thoroughly tested using unittesting. Test cases can be found in the [tests folder](https://github.com/mcrespoae/metrit/tree/main/tests).

## License

This project is licensed under the [MIT License](https://github.com/mcrespoae/metrit/blob/main/LICENSE).

## Contributors

- [Mario Crespo](https://github.com/mcrespoae)
