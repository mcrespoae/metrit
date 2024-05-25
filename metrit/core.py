import inspect
import time
from collections import deque
from functools import partial, wraps
from multiprocessing import Process, Queue, current_process
from sys import platform
from typing import Any, Callable, Dict, List, Tuple

import psutil

from metrit.Stats import Stats
from metrit.utils import check_is_recursive_func, extract_callable_and_args_if_method


class MetritConfig:
    ACTIVE: bool = True


def metrit(*args: Any, verbose: bool = False, look_for_children: bool = False) -> Callable:
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
        return partial(_decorator, verbose=verbose, look_for_children=look_for_children)


def _decorator(func: Callable, verbose: bool = False, look_for_children: bool = False) -> Callable:

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
        pid: int = current_process().pid  # type: ignore
        try:
            stats_to_sub: Stats = get_values_to_substract(pid, look_for_children)
        except Exception:
            stats_to_sub = Stats()

        result, measured_stats = call_func_and_measure_data(pid, callable_func, *args, **kwargs)
        cleaned_stats: Stats = measured_stats - stats_to_sub

        potential_recursion_func_stack.pop()
        if not potential_recursion_func_stack:
            cleaned_stats.print(verbose, callable_func.__name__, args_to_print, kwargs)
        return result

    return metrit_wrapper


def handle_recursive_call(func, potential_recursion_func_stack, *args, **kwargs) -> Any:
    result: Any = func(*args, **kwargs)
    potential_recursion_func_stack.pop()
    return result


def call_func_and_measure_data(pid: int | None, func: Callable, *args: Tuple, **kwargs: Dict) -> Tuple[Any, Stats]:
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

    result: Any = func(*args, **kwargs)

    finished_queue.put(True)  # Ensures the monitor process is terminated
    p_monitor.join()

    stats: Stats = monitor_queue.get()
    return result, stats


def get_values_to_substract(pid: int | None, look_for_children: bool) -> Stats:
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
    success_queue: Queue = Queue()

    p_pre_monitor: Process = Process(
        target=get_initial_snapshot_data, args=(pid, data_to_substract_queue, success_queue, look_for_children)
    )
    p_pre_monitor.start()

    if not success_queue.get():
        p_pre_monitor.terminate()
        stats_void = Stats()
        data_to_substract_queue.put(stats_void)
    else:
        p_pre_monitor.join()
    return data_to_substract_queue.get()


def get_initial_snapshot_data(
    pid: int | None, data_to_substract_queue: Queue, success_queue: Queue, look_for_children: bool
) -> None:
    """
    Get the initial snapshot data for a process with the given process ID.
    This data will be used later to substract it from the final read data.

    Args:
        pid (int | None): The process ID to get the initial snapshot data for.
        data_to_substract_queue (Queue): The queue to put the initial snapshot data into.

    Returns:
        None: This function does not return anything. It sends the initial snapshot data to the passed queue.
    """
    try:
        p: psutil.Process = psutil.Process(pid)

        _, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(p, 0.0, look_for_children)
        read_count, write_count, read_bytes, write_bytes = get_io_counters(p, look_for_children)
        stats = Stats(
            memory_percentage_avg=memory_percent,
            rss_bytes_avg=memory_rss,
            vms_bytes_avg=memory_vms,
            read_count=read_count,
            write_count=write_count,
            read_bytes=read_bytes,
            write_bytes=write_bytes,
        )
        success_queue.put(True)

    except Exception as e:
        success_queue.put(False)
        stats = Stats()
        print(f"Error getting initial snapshot data: {e}")
    finally:
        data_to_substract_queue.put(stats)


def get_process_by_pid(pid: int, refresh_rate: float) -> psutil.Process:
    timeout: float = 10.0
    while True:
        if pid is not None and psutil.pid_exists(pid):
            return psutil.Process(pid)
        else:
            time.sleep(refresh_rate)
            if timeout < 0:
                raise psutil.NoSuchProcess(pid)
            timeout -= refresh_rate


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

    refresh_rate: float = 0.1  # Initial refresh rate
    max_refresh_rate: int = 5  # Maximum refresh rate
    time_elapsed: float = 0.0

    try:
        p = get_process_by_pid(pid, refresh_rate)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Error getting process data: {e}")
        queue.put(Stats())
        return

    try:
        # TODO: Add support for network usage?
        cpu_usage_list: List[float] = []
        memory_rss_list: List[int] = []
        memory_vms_list: List[int] = []
        memory_percent_list: List[float] = []
        while True:
            total_cpu, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(p, refresh_rate, look_for_children)
            cpu_usage_list.append(total_cpu)
            memory_rss_list.append(memory_rss)
            memory_vms_list.append(memory_vms)
            memory_percent_list.append(memory_percent)

            if (not finished_queue.empty() and finished_queue.get()) or not p.is_running():
                read_count, write_count, read_bytes, write_bytes = get_io_counters(p, look_for_children)

                stats = Stats(
                    cpu_percentage_avg=sum(cpu_usage_list) / len(cpu_usage_list),
                    cpu_percentage_max=max(cpu_usage_list),
                    memory_percentage_avg=sum(memory_percent_list) / len(memory_percent_list),
                    rss_bytes_avg=sum(memory_rss_list) / len(memory_rss_list),
                    rss_bytes_max=max(memory_rss_list),
                    vms_bytes_avg=sum(memory_vms_list) / len(memory_vms_list),
                    vms_bytes_max=max(memory_vms_list),
                    read_count=read_count,
                    write_count=write_count,
                    read_bytes=read_bytes,
                    write_bytes=write_bytes,
                )
                queue.put(stats)
                return
            time.sleep(refresh_rate)
            time_elapsed += refresh_rate
            if time_elapsed > 10:
                if refresh_rate < max_refresh_rate:
                    refresh_rate = min(refresh_rate * 2, max_refresh_rate)
                    # Double the refresh rate, but do not exceed max_refresh_rate
                time_elapsed = 0.0
    except Exception as e:
        print(f"Error getting data: {e}")
        queue.put(Stats())
        return


def get_total_cpu_memory(
    p: psutil.Process, refresh_rate: float, look_for_children: bool = False
) -> Tuple[float, int, int, float]:
    try:
        total_cpu = p.cpu_percent(interval=refresh_rate)
        memory_info = p.as_dict(attrs=["memory_info", "memory_percent"])

        # Extract the values
        memory_percent = memory_info["memory_percent"]
        total_rss = memory_info["memory_info"].rss
        total_vms = memory_info["memory_info"].vms

        if look_for_children:
            i = 0
            for child in p.children(recursive=True):
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

        return total_cpu, total_rss, total_vms, memory_percent
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0, 0, 0, 0.0


def get_io_counters(process: psutil.Process, look_for_children: bool = False) -> Tuple[int, int, int, int]:
    read_count = 0
    write_count = 0
    read_bytes = 0
    write_bytes = 0
    if platform != "darwin":
        try:
            io_counters = process.io_counters()  # type: ignore
            read_count = io_counters.read_count
            write_count = io_counters.write_count
            read_bytes = io_counters.read_bytes
            write_bytes = io_counters.write_bytes

            if look_for_children:
                # Add child processes' I/O counters
                for child in process.children(recursive=True):
                    try:
                        child_io_counters = child.io_counters()  # type: ignore
                        read_count += child_io_counters.read_count
                        write_count += child_io_counters.write_count
                        read_bytes += child_io_counters.read_bytes
                        write_bytes += child_io_counters.write_bytes
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
    return read_count, write_count, read_bytes, write_bytes
