from collections import deque
from typing import Callable, Tuple

from multiprocess import Queue  # type: ignore


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
            if unit == "B":
                return f"{bytes_size:.0f}{unit}"
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f}PB"  # If it exceeds TB, convert to petabytes


def extract_callable_and_args_if_method(func: Callable, *args: Tuple) -> Tuple[Callable, Tuple, Tuple, bool]:
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
    return callable_func, args, args_to_print, is_method


def check_is_recursive_func(
    func: Callable, called_func_stack: deque[Callable], called_isolated_func_queue: Queue
) -> bool:
    """
    Checks if the function is being called recursively by checking the stack of called functions.
    It will send a warning if the function is being called recursively.
    Args:
        func (Callable): The function to check for recursion.
        called_func_stack (deque[Callable]): A stack of potential recursive functions.
    Returns:
        bool: True if the function is being called recursively, False otherwise.

    """
    is_recursive = False
    if not called_isolated_func_queue.empty():

        prev_func = called_isolated_func_queue.get()
        called_isolated_func_queue.put(prev_func)
        if (
            (prev_func.__name__ == func.__name__)
            and (prev_func.__module__ == func.__module__)  # noqa: W503
            and (prev_func.__code__.co_code == func.__code__.co_code)  # noqa: W503
        ):
            is_recursive = True

    if called_func_stack and called_func_stack[-1] == func:
        if is_recursive:
            # This means that it is recursive and it has been called from another process (isolate) so we need to append the same function again
            called_func_stack.append(func)
        is_recursive = True

    called_func_stack.append(func)
    return is_recursive
