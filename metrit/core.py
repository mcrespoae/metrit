import inspect
from collections import deque
from functools import partial, wraps
from typing import Any, Callable, Dict, Tuple

from multiprocess import Queue  # type: ignore

from metrit.Monitoring import Monitoring
from metrit.utils import check_is_recursive_func, extract_callable_and_args_if_method


class MetritConfig:
    ACTIVE: bool = True


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
        - If isolate==True and it crashes in the process, it will be tried again in the main process.



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
        nonlocal called_func_stack
        global called_isolated_func_queue

        is_recursive: bool = check_is_recursive_func(func, called_func_stack, called_isolated_func_queue)

        callable_func, args, args_to_print, is_method = extract_callable_and_args_if_method(func, *args)
        if is_recursive:
            return handle_recursive_call(callable_func, called_func_stack, called_isolated_func_queue, *args, **kwargs)

        crashed: bool = False
        if isolate and not is_method:
            try:
                result, pool_monitor_data = isolate_function(find_children, callable_func, *args, **kwargs)
            except Exception:
                crashed = True

        if crashed or not isolate or is_method:
            result, pool_monitor_data = call_func(find_children, callable_func, *args, **kwargs)

        called_func_stack.pop()
        if not called_isolated_func_queue.empty():
            called_isolated_func_queue.get()  # Consume the queue

        if not called_func_stack and called_isolated_func_queue.empty():
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
    result: Any = func(*args, **kwargs)

    called_func_stack.pop()
    if not called_isolated_func_queue.empty():
        called_isolated_func_queue.get()  # Consume one element of the queue
    return result


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
    except Exception as e:
        pool_monitor_data.stop_monitoring()
        import traceback

        traceback.print_exc()
        raise e

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
        Exception: If an exception occurs during the execution of the function.
        This exception will be handled in the main process and try again the execution and measurement of the function in the main process.
    """
    from multiprocess import Process  # type: ignore

    data_queue = Queue()
    result_queue = Queue()
    error_queue = Queue()

    try:

        func_process: Process = Process(
            target=call_func_isolated,
            args=(find_children, func, data_queue, result_queue, error_queue, args),
            kwargs=kwargs,
        )

        func_process.start()
        func_process.join()
        if not error_queue.empty():
            raise error_queue.get()

        pool_monitor_data = data_queue.get()
        result = result_queue.get()
        result_queue.close()
        data_queue.close()

        return result, pool_monitor_data

    except Exception as e:
        func_process.join()
        func_process.terminate()
        print("Error trying to isolate the process. Trying it again in main process:", e)
        raise e


def call_func_isolated(
    find_children: bool,
    func: Callable,
    data_queue: Queue,
    result_queue: Queue,
    error_queue: Queue,
    args: Tuple,
    **kwargs: Dict,
):
    """
    Executes the given function in a separate process and monitors its resource usage.

    Args:
        find_children (bool): Whether to find child processes.
        func (Callable): The function to be executed.
        data_queue (Queue): The queue to store the monitoring data.
        result_queue (Queue): The queue to store the result of the function.
        error_queue (Queue): The queue to store any exceptions that occur during execution.
        args (Tuple): The positional arguments to be passed to the function.
        **kwargs (Dict): The keyword arguments to be passed to the function.

    Returns:
        None

    Raises:
        Exception: If an exception occurs during the execution of the function.
            The exception is put into the error_queue.

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
        error_queue.put(e)
        return

    pool_monitor_data.stop_monitoring()
    pool_monitor_data.calculate_delta(pre_monitor_data)
    data_queue.put(pool_monitor_data)
    result_queue.put(result)
