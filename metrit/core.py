import inspect
from collections import deque
from functools import partial, wraps
from typing import Any, Callable, Dict, Tuple

from metrit.Monitoring import Monitoring
from metrit.utils import check_is_recursive_func, extract_callable_and_args_if_method


class MetritConfig:
    ACTIVE: bool = True


def metrit(*args: Any, verbose: bool = False, find_children: bool = False) -> Callable:
    """
    Decorator function that measures the cpu, ram and io footprint of a given function in the current process. It can be called like @metrit or using arguments @metrit(...)

    Args:
        args: contains the function to be decorated if no arguments are provided when calling the decorator
        verbose (bool, optional): Whether to print detailed information after execution. Defaults to False.

    Returns:
        Callable: The decorated function if arguments are provided, otherwise a partial function.
                    If the callable is a class it will be returned unmodified and will not be decorated.
                    If the TempitConfig ACTIVE flag is set to false, the callable will be returned without modification and will not be decorated.

    Raises:
        Exception: If the function crashes, it will raise the exception given by the user's function.

    Notes:
        - Processes spawned inside the decorated function won't be measured
        - This decorator also checks for recursion automatically even though is better to wrap the recursive function in another function and apply the @metrit decorator to the new function.
        - Classes will be returned unmodified and will not be decorated.
        - If the function is a method, the first argument will be removed from `args_to_print`.
        - If the function is a class method, the first argument will be replaced with the class itself.
        - If the function is a static method, the first argument will be removed.



    Example:
        @metrit(verbose=True)
        def my_function(arg1, arg2):
            # function body

        @metrit
        def my_function(arg1, arg2):
            # function body

        # The decorated function can be used as usual
        result = my_function(arg1_value, arg2_value)
    """
    if not MetritConfig.ACTIVE:
        # Return the callable unmodified if MetritConfig.ACTIVE is set to False
        if args:
            return args[0]
        else:
            return lambda f: f
    if args:  # If arguments are provided, return the decorated function
        return _decorator(*args)
    else:
        return partial(_decorator, verbose=verbose, find_children=find_children)


def _decorator(func: Callable, verbose: bool = False, find_children: bool = False) -> Callable:

    if inspect.isclass(func):
        # If a class is found, return the class inmediatly since it could raise an exception if triggered from other processes
        return func
    potential_recursion_func_stack: deque[Callable] = deque()

    @wraps(func)
    def metrit_wrapper(*args: Tuple, **kwargs: Dict) -> Any:
        nonlocal potential_recursion_func_stack
        is_recursive: bool = check_is_recursive_func(func, potential_recursion_func_stack)
        callable_func, args, args_to_print = extract_callable_and_args_if_method(func, *args)
        if is_recursive:
            return handle_recursive_call(callable_func, potential_recursion_func_stack, *args, **kwargs)

        # Get the memory footprint before the function is called

        pre_monitor_data = Monitoring(find_children=find_children)
        pre_monitor_data.take_snapshot()

        pool_monitor_data = Monitoring(find_children=find_children)
        pool_monitor_data.start_monitoring()
        try:
            result = callable_func(*args, **kwargs)
        except Exception as e:
            pool_monitor_data.stop_monitoring()
            raise e

        pool_monitor_data.stop_monitoring()
        pool_monitor_data.calculate_delta(pre_monitor_data)

        potential_recursion_func_stack.pop()
        if not potential_recursion_func_stack:
            pool_monitor_data.print(verbose, callable_func.__name__, args_to_print, kwargs)

        return result

    return metrit_wrapper


def handle_recursive_call(func, potential_recursion_func_stack, *args, **kwargs) -> Any:
    """
    Handle a recursive call by executing the given function with the provided arguments and keyword arguments.

    Parameters:
        func (Callable): The function to be executed.
        potential_recursion_func_stack (deque): A stack of potential recursive functions.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        Any: The result of executing the function.
    """
    result: Any = func(*args, **kwargs)
    potential_recursion_func_stack.pop()
    return result
