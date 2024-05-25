import inspect
import time
import warnings
from collections import deque
from functools import partial, wraps
from multiprocessing import Process, Queue, current_process
from typing import Any, Callable, Dict, List, Tuple

import psutil

from measurit.utils import print_usage


class MeasuritConfig:
    ACTIVE: bool = True


def measureit(*args: Any, verbose: bool = False) -> Callable:
    """
    Decorator function that measures the cpu, ram and io footprint of a given function in the current process. It can be called like @measurit or using arguments @measurit(...)

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
        - This decorator also checks for recursion automatically even though is better to wrap the recursive function in another function and apply the @measurit decorator to the new function.
        - Classes will be returned unmodified and will not be decorated.
        - If the function is a method, the first argument will be removed from `args_to_print`.
        - If the function is a class method, the first argument will be replaced with the class itself.
        - If the function is a static method, the first argument will be removed.



    Example:
        @measurit(verbose=True)
        def my_function(arg1, arg2):
            # function body

        @measurit
        def my_function(arg1, arg2):
            # function body

        # The decorated function can be used as usual
        result = my_function(arg1_value, arg2_value)
    """
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
            try:
                memory_rss_to_substract, memory_vms_to_substract, io_data_to_substract = get_values_to_substract(pid)
            except Exception:
                memory_rss_to_substract = 0
                memory_vms_to_substract = 0
                io_data_to_substract = {
                    "read_count": 0,
                    "write_count": 0,
                    "read_bytes": 0,
                    "write_bytes": 0,
                }

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
    pid: int | None, func: Callable, *args: Tuple, **kwargs: Dict
) -> Tuple[Any, List[float], List[int], List[int], Dict[str, int]]:
    """
    Calls a function and measures its CPU usage, memory usage, and I/O usage.
    Args:
        pid (int | None): The process ID of the function to monitor. Int is expected since the process measured is the current process.
        func (Callable): The function to call.
        *args (Tuple): The positional arguments to pass to the function.
        **kwargs (Dict): The keyword arguments to pass to the function.
    Returns:
        Tuple[Any, List[float], List[int], List[int], Dict[str, int]]: A tuple containing the result of the function,
        a list of CPU usage percentages, a list of memory RSS values, a list of memory VMS values, and a dictionary
        containing I/O data.
    """

    # Start the necessary quesues and process
    monitor_queue: Queue = Queue()
    finished_queue: Queue = Queue()

    p_monitor: Process = Process(target=monitor_process_pooling, args=(pid, monitor_queue, finished_queue))
    p_monitor.start()
    # TODO: Add support for children if the function can be triggered in other process - Done but not in production

    try:
        result: Any = func(*args, **kwargs)  # Not isolated way
    finally:
        finished_queue.put(True)  # Ensures the monitor process is terminated
        p_monitor.join()

    cpu_usage_list, memory_rss_list, memory_vms_list, io_data = monitor_queue.get()
    return result, cpu_usage_list, memory_rss_list, memory_vms_list, io_data


def get_values_to_substract(pid: int | None) -> Tuple[int, int, Dict[str, int]]:
    """
    Get initial values to substract them later. This triggers a new process to avoid overhead of the current process.

    Args:
        pid (int | None): The process ID to get the initial values for.

    Returns:
        Tuple[int, int, Dict[str, int]]: A tuple containing the initial values to substract:
            - int: The initial memory RSS value.
            - int: The initial memory VMS value.
            - Dict[str, int]: A dictionary containing the initial I/O data:
                - "read_count": The initial read count.
                - "write_count": The initial write count.
                - "read_bytes": The initial read bytes.
                - "write_bytes": The initial write bytes.
    """
    data_to_substract_queue: Queue = Queue()
    p_pre_monitor: Process = Process(target=get_initial_snapshot_data, args=(pid, data_to_substract_queue))
    p_pre_monitor.start()
    p_pre_monitor.join()
    return data_to_substract_queue.get()


def get_initial_snapshot_data(pid: int | None, data_to_substract_queue: Queue) -> None:
    """
    Get the initial snapshot data for a process with the given process ID.
    This data will be used later to substract it from the final read data.

    Args:
        pid (int | None): The process ID to get the initial snapshot data for.
        data_to_substract_queue (Queue): The queue to put the initial snapshot data into.

    Returns:
        None: This function does not return anything. It sends the initial snapshot data to the passed queue.
    """
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


def monitor_process_pooling(pid: int, queue: Queue, finished_queue: Queue, look_for_children: bool = False) -> None:
    """
    Monitors a process with the given PID to retrieve CPU, memory, and I/O usage data.

    Args:
        pid (int): The process ID to monitor.
        queue (Queue): A multiprocessing Queue to store the CPU, memory, and I/O usage data.
        finished_queue (Queue): A multiprocessing Queue to signal the end of monitoring.
        look_for_children (bool, optional): Whether to include child processes in the monitoring. Defaults to False.

    Returns:
        None: This function does not return anything. It sends the CPU, memory, and I/O usage data to the passed queue.
    """
    # TODO: Add support for network usage?
    cpu_usage_list: List[float] = []
    memory_rss_list: List[int] = []
    memory_vms_list: List[int] = []
    io_data: Dict[str, int] = {}
    refresh_rate: float = 0.1  # Initial refresh rate
    max_refresh_rate: int = 5  # Maximum refresh rate
    time_elapsed: float = 0.0
    timeout: float = 10.0

    while True:
        try:
            if pid is not None and psutil.pid_exists(pid):
                p: psutil.Process = psutil.Process(pid)
                break
            else:
                time.sleep(refresh_rate)
                if timeout < 0:
                    raise psutil.NoSuchProcess(pid)
                timeout -= refresh_rate

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            queue.put(([0], [0], [0], {"read_count": 0, "write_count": 0, "read_bytes": 0, "write_bytes": 0}))
            return

    def get_total_cpu_memory(
        process: psutil.Process, refresh_rate: float, look_for_children: bool = False
    ) -> Tuple[float, int, int]:
        try:
            total_cpu = process.cpu_percent(interval=refresh_rate)
            memory_info = process.memory_info()
            total_rss = memory_info.rss
            total_vms = memory_info.vms

            if look_for_children:
                i = 0
                for child in process.children(recursive=True):
                    try:

                        # TODO: Maybe here we can get up to 100% CPU usage since it could be distributed through multiple processors.
                        total_cpu += child.cpu_percent(interval=refresh_rate)
                        child_memory_info = child.memory_info()
                        total_rss += child_memory_info.rss
                        total_vms += child_memory_info.vms
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    i += 1

                if i > 0:
                    # Get the avg CPU usage. Try with num_cores = psutil.cpu_count() and divide total_cpu by num_cores to get a maybe more accurate CPU usage.
                    # It won't show 100% if only one processor is used because it is distributed through multiple processors.
                    total_cpu = total_cpu / i

            return total_cpu, total_rss, total_vms
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0, 0, 0

    def get_io_counters(process: psutil.Process, look_for_children: bool = False) -> Dict[str, int]:
        try:
            io_counters = process.io_counters()
            io_data = {
                "read_count": io_counters.read_count,
                "write_count": io_counters.write_count,
                "read_bytes": io_counters.read_bytes,
                "write_bytes": io_counters.write_bytes,
            }

            if look_for_children:
                # Add child processes' I/O counters
                for child in process.children(recursive=True):
                    print("CHILDREN COUNTER")
                    try:
                        child_io_counters = child.io_counters()
                        io_data["read_count"] += child_io_counters.read_count
                        io_data["write_count"] += child_io_counters.write_count
                        io_data["read_bytes"] += child_io_counters.read_bytes
                        io_data["write_bytes"] += child_io_counters.write_bytes
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            io_data = {"read_count": 0, "write_count": 0, "read_bytes": 0, "write_bytes": 0}
        return io_data

    while True:
        total_cpu, total_rss, total_vms = get_total_cpu_memory(p, refresh_rate, look_for_children)
        cpu_usage_list.append(total_cpu)
        memory_rss_list.append(total_rss)
        memory_vms_list.append(total_vms)

        if (not finished_queue.empty() and finished_queue.get()) or not p.is_running():
            io_data = get_io_counters(p, look_for_children)
            queue.put((cpu_usage_list, memory_rss_list, memory_vms_list, io_data))
            return
        time.sleep(refresh_rate)
        time_elapsed += refresh_rate
        if time_elapsed > 10:
            if refresh_rate < max_refresh_rate:
                refresh_rate = min(refresh_rate * 2, max_refresh_rate)
                # Double the refresh rate, but do not exceed max_refresh_rate
            time_elapsed = 0.0


def substract_data(
    memory_rss_to_substract: int,
    memory_rss_list: List[int],
    memory_vms_list_to_substract: int,
    memory_vms_list: List[int],
    io_data_to_substract: Dict[str, int],
    io_data: Dict[str, int],
) -> Tuple[List[int], List[int], Dict[str, int]]:
    """
    Subtracts the given values from the memory and IO data lists.
    Args:
        memory_rss_to_substract (int): The value to subtract from the memory RSS list.
        memory_rss_list (List[int]): The list of memory RSS values.
        memory_vms_list_to_substract (int): The value to subtract from the memory VMS list.
        memory_vms_list (List[int]): The list of memory VMS values.
        io_data_to_substract (Dict[str, int]): The dictionary of IO data values to subtract.
        io_data (Dict[str, int]): The dictionary of IO data values.
    Returns:
        Tuple[List[int], List[int], Dict[str, int]]: A tuple containing the cleaned memory RSS list,
        cleaned memory VMS list, and cleaned IO data dictionary.
    """
    cleaned_memory_rss_list: List[int] = [max(x - memory_rss_to_substract, 0) for x in memory_rss_list]
    cleaned_memory_vms_list: List[int] = [max(x - memory_vms_list_to_substract, 0) for x in memory_vms_list]
    cleaned_io_data: Dict[str, int] = {
        key: max(io_data[key] - io_data_to_substract[key], 0) for key in io_data if key in io_data_to_substract
    }

    return cleaned_memory_rss_list, cleaned_memory_vms_list, cleaned_io_data
