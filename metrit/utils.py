from collections import deque
from typing import Callable, Tuple
from warnings import warn


def format_size(bytes_size: int | float) -> str:
    """
    Converts a size in bytes to a human-readable format.
    Parameters:
        bytes_size (int | float): The size in bytes to be converted.
    Returns:
        str: The human-read
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} PB"  # If it exceeds TB, convert to petabytes


def extract_callable_and_args_if_method(func: Callable, *args: Tuple) -> Tuple[Callable, Tuple, Tuple]:
    """
    Extracts the callable function and arguments from a given function, if it is a method.
    Args:
        func (Callable): The function to extract the callable from.
        *args: Variable length argument list.
    Returns:
        Tuple[Callable, Tuple, Tuple]: A tuple containing the extracted callable function, the modified arguments,
        and the arguments to be printed.
    """

    callable_func: Callable = func
    args_to_print: Tuple = args
    is_method: bool = hasattr(args[0], func.__name__) if args else False

    if is_method:
        args_to_print = args[1:]
        if isinstance(func, classmethod):
            args = (args[0].__class__,) + args[1:]  # type: ignore
            callable_func = func.__func__
        elif isinstance(func, staticmethod):
            args = args[1:]
    return callable_func, args, args_to_print


def check_is_recursive_func(func: Callable, potential_recursion_func_stack: deque[Callable]) -> bool:
    """
    Checks if the function is being called recursively by checking the stack of called functions.
    It will send a warning if the function is being called recursively.
    Args:
        func (Callable): The function to check for recursion.
        potential_recursion_func_stack (deque[Callable]): A stack of potential recursive functions.
    Returns:
        bool: True if the function is being called recursively, False otherwise.

    """

    if potential_recursion_func_stack and potential_recursion_func_stack[-1] == func:
        potential_recursion_func_stack.append(func)
        # Check if the function is being called recursively by checking the object identity. This is way faster than using getFrameInfo
        warning_msg = "Recursive function detected. This process may be slow. Consider wrapping the recursive function in another function and applying the @tempit decorator to the new function."
        warn(warning_msg, stacklevel=3)
        return True
    potential_recursion_func_stack.append(func)
    return False
