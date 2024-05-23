import inspect
import time
import warnings
from collections import deque
from functools import partial, wraps
from multiprocessing import Process, Queue, current_process
from typing import Any, Callable, Dict, List, Tuple

import psutil

from measurit.utils import print_usage, substract_data


class MeasuritConfig:
    ACTIVE: bool = True


def measureit(*args: Any, verbose: bool = False) -> Callable:

    if not MeasuritConfig.ACTIVE:
        # Return the callable unmodified if MeasuritConfig.ACTIVE is set to False
        if args:
            return args[0]
        else:
            return lambda f: f

    def decorator(func: Callable, verbose: bool = False) -> Callable:

        if inspect.isclass(func):
            # If a class is found, return the class inmediatly since it could raise an exception if triggered from other processes
            return func
        potential_recursion_func_stack: deque[Callable] = deque()

        @wraps(func)
        def measureit_wrapper(*args: Tuple, **kwargs: Dict) -> Any:
            nonlocal potential_recursion_func_stack
            is_recursive: bool = check_is_recursive_func(func, potential_recursion_func_stack)
            callable_func, args, args_to_print = extract_callable_and_args_if_method(func, *args)
            if is_recursive:
                result: Any = callable_func(*args, **kwargs)
                potential_recursion_func_stack.pop()
                return result

            # Get the memory footprint before the function is called
            pid: int = current_process().pid  # type: ignore
            memory_rss_to_substract, memory_vms_to_substract, io_data_to_substract = get_values_to_substract(pid)

            result, cpu_usage_list, memory_rss_list, memory_vms_list, io_data = call_func_and_measure_data(
                pid, callable_func, *args, **kwargs
            )

            cleaned_memory_rss_list, cleaned_memory_vms_list, clenaed_io_data = substract_data(
                memory_rss_to_substract,
                memory_rss_list,
                memory_vms_to_substract,
                memory_vms_list,
                io_data_to_substract,
                io_data,
            )
            potential_recursion_func_stack.pop()
            if not potential_recursion_func_stack:
                print_usage(
                    callable_func.__name__,
                    args_to_print,
                    kwargs,
                    cpu_usage_list,
                    cleaned_memory_rss_list,
                    cleaned_memory_vms_list,
                    clenaed_io_data["write_count"],
                    clenaed_io_data["read_count"],
                    clenaed_io_data["write_bytes"],
                    clenaed_io_data["read_bytes"],
                    verbose,
                )

            return result

        return measureit_wrapper

    if args:  # If arguments are not provided, return a decorator
        return decorator(*args)

    else:
        return partial(decorator, verbose=verbose)


def call_func_and_measure_data(
    pid: int | None, callable_func: Callable, *args: Tuple, **kwargs: Dict
) -> Tuple[Any, List[float], List[int], List[int], Dict[str, int]]:
    # Start the necessary quesues and process
    monitor_queue: Queue = Queue()
    finished_queue: Queue = Queue()
    p_monitor: Process = Process(target=monitor_process_pooling, args=(pid, monitor_queue, finished_queue))
    p_monitor.start()
    try:
        result: Any = callable_func(*args, **kwargs)
    finally:
        finished_queue.put(True)  # Ensures the monitor process is terminated
    p_monitor.join()
    cpu_usage_list, memory_rss_list, memory_vms_list, io_data = monitor_queue.get()
    return result, cpu_usage_list, memory_rss_list, memory_vms_list, io_data


def get_values_to_substract(pid: int | None) -> Tuple[int, int, Dict[str, int]]:
    # Get initial values to substract them later. Maybe put this into a process to avoid overhead
    data_to_substract_queue: Queue = Queue()
    p_pre_monitor: Process = Process(target=get_initial_snapshot_data, args=(pid, data_to_substract_queue))
    p_pre_monitor.start()
    p_pre_monitor.join()
    return data_to_substract_queue.get()


def get_initial_snapshot_data(pid: int | None, data_to_substract_queue: Queue) -> None:
    p: psutil.Process = psutil.Process(pid)
    memory_info = p.memory_info()
    memory_rss: int = memory_info.rss
    memory_vms: int = memory_info.vms
    io_counters = p.io_counters()
    io_data: Dict[str, int] = {
        "read_count": io_counters.read_count,
        "write_count": io_counters.write_count,
        "read_bytes": io_counters.read_bytes,
        "write_bytes": io_counters.write_bytes,
    }
    data_to_substract_queue.put((memory_rss, memory_vms, io_data))


def check_is_recursive_func(func: Callable, potential_recursion_func_stack: deque[Callable]) -> bool:
    """
    Checks if the function is being called recursively.
    Returns:
        Tuple[List[Callable], int, bool]: A tuple containing the potential recursive function stack to check if the function is being called recursively, None otherwise.
        The second element is the run_times parameter, and the third element is a boolean indicating if concurrent_execution is enabled.
    """

    if potential_recursion_func_stack and potential_recursion_func_stack[-1] == func:
        potential_recursion_func_stack.append(func)
        # Check if the function is being called recursively by checking the object identity. This is way faster than using getFrameInfo
        warning_msg = "Recursive function detected. This process may be slow. Consider wrapping the recursive function in another function and applying the @tempit decorator to the new function."
        warnings.warn(warning_msg, stacklevel=3)
        return True
    potential_recursion_func_stack.append(func)
    return False


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


def monitor_process_pooling(pid: int, queue: Queue, finished_queue: Queue) -> None:
    # TODO: Add support for network usage?
    cpu_usage_list: List[float] = []
    memory_rss_list: List[int] = []
    memory_vms_list: List[int] = []
    io_data: Dict[str, int] = {}
    refresh_rate: float = 0.1  # Initial refresh rate
    max_refresh_rate: int = 5  # Maximum refresh rate
    time_elapsed: float = 0.0

    p: psutil.Process = psutil.Process(pid)

    while True:

        cpu_usage: float = p.cpu_percent(interval=refresh_rate)
        memory_info = p.memory_info()
        cpu_usage_list.append(cpu_usage)
        memory_rss_list.append(memory_info.rss)
        memory_vms_list.append(memory_info.vms)

        if not finished_queue.empty() and finished_queue.get():
            io_counters = p.io_counters()
            io_data = {
                "read_count": io_counters.read_count,
                "write_count": io_counters.write_count,
                "read_bytes": io_counters.read_bytes,
                "write_bytes": io_counters.write_bytes,
            }
            queue.put((cpu_usage_list, memory_rss_list, memory_vms_list, io_data))
            return
        time.sleep(refresh_rate)
        time_elapsed += refresh_rate
        if time_elapsed > 10:
            if refresh_rate < max_refresh_rate:
                refresh_rate = min(refresh_rate * 2, max_refresh_rate)
                # Double the refresh rate, but do not exceed max_refresh_rate
            time_elapsed = 0.0
