import inspect
import traceback
from collections import deque
from functools import partial, wraps
from typing import Any, Callable, Dict, Tuple

from multiprocess import Queue  # type: ignore

from metrit.Monitoring import Monitoring
from metrit.utils import check_is_recursive_func, extract_callable_and_args_if_method

# How often to poll the isolated process' result queue while it runs. Polling (and
# draining) while the process is alive prevents a large return value from filling the
# queue pipe and deadlocking the child, and lets us detect a hard crash (segfault,
# os._exit, SIGKILL... ) that never reports a result.
_ISOLATED_POLL_INTERVAL: float = 0.1


class MetritConfig:
    ACTIVE: bool = True


class IsolationError(Exception):
    """
    Raised internally when the isolation machinery itself fails, i.e. when the
    isolated process crashed without handing back a result. It signals that the
    decorated callable should be retried in the main process.

    User exceptions raised by the decorated callable are *never* wrapped in this
    error; they are propagated as-is so the callable is not executed twice.
    """


called_isolated_func_queue = Queue()


def metrit(*args: Any, verbose: bool = False, find_children: bool = False, isolate: bool = True) -> Callable:
    """
    Decorator function that measures the cpu, ram and io footprint of a given function in the current process. It can be called like @metrit or using arguments @metrit(...)

    Args:
        args: contains the function to be decorated if no arguments are provided when calling the decorator
        verbose (bool, optional): Whether to print detailed information after execution. Defaults to False.
        isolate (bool, optional): If True, tries to encapsulate the function in its own process. Defaults to True.

    Returns:
        Callable: The decorated function if arguments are provided, otherwise a partial function.
                    If the callable is a class it will be returned unmodified and will not be decorated.
                    If the MetritConfig ACTIVE flag is set to false, the callable will be returned without modification and will not be decorated.

    Raises:
        Exception: If the function crashes, it will raise the exception given by the user's function.

    Notes:
        - Processes spawned inside the decorated function won't be measured
        - This decorator also checks for recursion automatically even though is better to wrap the recursive function in another function and apply the @metrit decorator to the new function.
        - Classes will be returned unmodified and will not be decorated.
        - If the function is a method, it won't be isolated.
        - If isolate==True and the isolated process crashes (not a user exception), the function will be tried again in the main process. Exceptions raised by the user's function are propagated as-is and the function is not executed a second time.



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
        return partial(_decorator, verbose=verbose, find_children=find_children, isolate=isolate)


def _decorator(func: Callable, verbose: bool = False, find_children: bool = False, isolate: bool = True) -> Callable:
    """
    Decorator function that measures the memory and time of a given function.
    Args:
        func (Callable): The function to be decorated.
        verbose (bool, optional): If True, prints detailed information about the function execution. Defaults to False.
        find_children (bool, optional): If True, measures the memory and time of all child processes spawned by the function. Defaults to False.
        isolate (bool, optional): If True, encapsulates the function in its own process. Defaults to True.

    Returns:
        Callable: The decorated function.
    Raises:
        Exception: If the function crashes, it will raise the exception given by the user's function.
    """
    if inspect.isclass(func):
        # If a class is found, return the class inmediatly since it could raise an exception if triggered from other processes
        return func

    called_func_stack: deque[Callable] = deque()

    @wraps(func)
    def metrit_wrapper(*args: Tuple, **kwargs: Dict) -> Any:
        is_recursive: bool = check_is_recursive_func(func, called_func_stack, called_isolated_func_queue)

        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(func, *args)
        if is_recursive:
            return handle_recursive_call(callable_func, called_func_stack, called_isolated_func_queue, *args, **kwargs)

        crashed: bool = False
        result: Any = None
        pool_monitor_data: Monitoring | None = None
        try:
            if isolate and not is_method:
                try:
                    result, pool_monitor_data = isolate_function(find_children, callable_func, *args, **kwargs)
                except IsolationError as e:
                    crashed = True
                    print("metrit: isolation failed. Running the function in the main process:", e)

            if crashed or not isolate or is_method:
                result, pool_monitor_data = call_func(find_children, callable_func, *args, **kwargs)
        finally:
            # Always keep the recursion stack balanced, even if the callable raised.
            called_func_stack.pop()
            if not called_isolated_func_queue.empty():
                called_isolated_func_queue.get()  # Consume the queue

        if not called_func_stack and called_isolated_func_queue.empty():
            assert pool_monitor_data is not None
            pool_monitor_data.print(verbose, callable_func.__name__, args_to_print, kwargs)

        return result

    return metrit_wrapper


def handle_recursive_call(
    func: Callable, called_func_stack: deque, called_isolated_func_queue: Queue, *args: Tuple, **kwargs: Dict
) -> Any:
    """
    Handle a recursive call by executing the given function with the provided arguments and keyword arguments.

    Parameters:
        func (Callable): The function to be executed.
        called_func_stack (deque): A stack of potential recursive functions.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        Any: The result of executing the function.
    """
    try:
        return func(*args, **kwargs)
    finally:
        # Always keep the recursion stack balanced, even if the callable raised.
        called_func_stack.pop()
        if not called_isolated_func_queue.empty():
            called_isolated_func_queue.get()  # Consume one element of the queue


def call_func(find_children: bool, func: Callable, *args: Tuple, **kwargs: Dict) -> Tuple[Any, Monitoring]:
    """
    Calls the given function with the provided arguments and keyword arguments.
    Monitor the resources used by the function.
    Returns the result along with the monitoring data.

    Args:
        find_children (bool): Whether to find children processes.
        func (Callable): The function to be executed.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        Tuple[Any, Monitoring]: A tuple containing the result of the function and the monitoring data.

    Raises:
        Exception: If an exception occurs during the execution of the function.
    """

    pre_monitor_data = Monitoring(find_children=find_children)
    pre_monitor_data.take_snapshot()

    pool_monitor_data = Monitoring(find_children=find_children)
    pool_monitor_data.start_monitoring()
    try:
        result: Any = func(*args, **kwargs)
    except Exception:
        pool_monitor_data.stop_monitoring()
        raise

    pool_monitor_data.stop_monitoring()
    pool_monitor_data.calculate_delta(pre_monitor_data)
    return result, pool_monitor_data


def isolate_function(find_children: bool, func: Callable, *args: Tuple, **kwargs: Dict) -> Tuple[Any, Monitoring]:
    """
    Isolates the given function in a separate process and monitors its resource usage.
    Args:
        find_children (bool): Whether to find children processes.
        func (Callable): The function to be executed.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
    Returns:
        Tuple[Any, Monitoring]: A tuple containing the result of the function and the monitoring data.
    Raises:
        IsolationError: If the isolated process could not be started or crashed without
            reporting a result. The caller will retry the execution in the main process.
        Exception: Any exception raised by the user's function, propagated as-is so the
            function is not executed a second time.
    """
    from multiprocess import Process  # type: ignore

    result_queue: Queue = Queue()

    try:
        func_process: Process = Process(
            target=call_func_isolated,
            args=(find_children, func, result_queue, args),
            kwargs=kwargs,
        )
        func_process.start()
    except Exception as e:
        result_queue.close()
        raise IsolationError("Could not start the isolated process") from e

    # Drain the result queue while the process is running. Reading only after join()
    # would deadlock if the report is larger than the pipe buffer, and a timeout on a
    # blocking get() would hang forever if the process died without reporting.
    report = None
    while True:
        try:
            report = result_queue.get(timeout=_ISOLATED_POLL_INTERVAL)
            break
        except Exception:
            if func_process.exitcode is not None:
                # The process ended and no report arrived: it crashed.
                break

    func_process.join()
    exitcode = func_process.exitcode
    result_queue.close()

    if report is not None:
        status, payload = report
        if status == "ok":
            pool_monitor_data, result = payload
            return result, pool_monitor_data
        # The user's function raised: propagate without re-running it.
        raise payload

    raise IsolationError(f"The isolated process exited unexpectedly (exitcode={exitcode})")


def call_func_isolated(
    find_children: bool,
    func: Callable,
    result_queue: Queue,
    args: Tuple,
    **kwargs: Dict,
):
    """
    Executes the given function in a separate process and monitors its resource usage.

    A single tagged report is sent through ``result_queue``:
        - ("ok", (pool_monitor_data, result)) on success.
        - ("error", exception) if the user's function raised.

    If the process dies without sending a report (hard crash), nothing is queued and
    the parent detects it through the process exit code.

    Args:
        find_children (bool): Whether to find child processes.
        func (Callable): The function to be executed.
        result_queue (Queue): The queue to store the tagged report.
        args (Tuple): The positional arguments to be passed to the function.
        **kwargs (Dict): The keyword arguments to be passed to the function.

    Returns:
        None
    """
    global called_isolated_func_queue
    called_isolated_func_queue.put(func)
    pre_monitor_data = Monitoring(find_children=find_children)
    pre_monitor_data.take_snapshot()
    pool_monitor_data = Monitoring(find_children=find_children)
    pool_monitor_data.start_monitoring()

    try:
        result: Any = func(*args, **kwargs)
    except Exception as e:
        pool_monitor_data.stop_monitoring()
        called_isolated_func_queue.get()
        e.add_note("Original traceback:\n" + traceback.format_exc())
        result_queue.put(("error", e))
        return

    pool_monitor_data.stop_monitoring()
    pool_monitor_data.calculate_delta(pre_monitor_data)
    result_queue.put(("ok", (pool_monitor_data, result)))
