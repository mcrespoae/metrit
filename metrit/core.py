import inspect
import os
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
            stats_to_sub, children_stats_to_sub_list = get_values_to_substract(pid, look_for_children)
        except Exception:
            stats_to_sub = Stats()
            children_stats_to_sub_list = []

        result, measured_stats = call_func_and_measure_data(pid, callable_func, *args, **kwargs)
        cleaned_stats: Stats = measured_stats - stats_to_sub

        potential_recursion_func_stack.pop()
        if not potential_recursion_func_stack:
            cleaned_stats.print(verbose, callable_func.__name__, args_to_print, kwargs)
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


def call_func_and_measure_data(pid: int | None, func: Callable, *args: Tuple, **kwargs: Dict) -> Tuple[Any, Stats]:
    """
    Calls a function and measures its CPU usage, memory usage, and I/O usage.
    Args:
        pid (int | None): The process ID of the function to monitor. Int is expected since the process measured is the current process.
        func (Callable): The function to call.
        *args (Tuple): The positional arguments to pass to the function.
        **kwargs (Dict): The keyword arguments to pass to the function.
    Returns:
        Tuple[Any, Stats]: A tuple containing the result of the function and the Stats object.
        Stats: Object containing the CPU usage, memory usage, and I/O usage of the function.
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


def get_values_to_substract(pid: int | None, look_for_children: bool) -> Tuple[Stats, List[Stats]]:
    """
    Get initial values to substract them later. This triggers a new process to avoid overhead of the current process.

    Args:
        pid (int | None): The process ID to get the initial values for.
        look_for_children (bool): Whether to look for children processes or not.

    Returns:
        Stats: Object containing the initial values to substract them later.
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
        children_stats_to_sub_list: List[Stats] = []
        data_to_substract_queue.put((stats_void, children_stats_to_sub_list))
    else:
        p_pre_monitor.join()
    return data_to_substract_queue.get()


def get_initial_snapshot_data(
    pid: int | None, data_to_substract_queue: Queue, success_queue: Queue, look_for_children: bool
) -> None:
    """
    Get the initial snapshot data for a process with the given process ID.
    This data will be used later to substract it from the final read data.
    If it fails, it will add a default Stats object to the queue.

    Args:
        pid (int | None): The process ID to get the initial snapshot data for.
        data_to_substract_queue (Queue): The queue to put the initial snapshot data into.
        success_queue (Queue): The queue to put whether the initial snapshot data was successfully obtained.
        look_for_children (bool): Whether to look for children processes or not.

    Returns:
        None: This function does not return anything. It sends the initial snapshot data to the passed data_to_substract_queue.
    """
    try:
        p: psutil.Process = psutil.Process(pid)
        _, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(p, 0.0)
        read_count, write_count, read_bytes, write_bytes = get_io_counters(p)
        stats = Stats(
            pid=p.pid,
            memory_percentage_avg=memory_percent,
            rss_bytes_avg=memory_rss,
            vms_bytes_avg=memory_vms,
            read_count=read_count,
            write_count=write_count,
            read_bytes=read_bytes,
            write_bytes=write_bytes,
        )
        children_stats_list: List[Stats] = []
        if look_for_children:
            for child in p.children(recursive=True):
                if child.pid == os.getpid():  # Avoid counting the current process
                    continue
                _, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(child, 0.0)
                read_count, write_count, read_bytes, write_bytes = get_io_counters(child)
                child_stats = Stats(
                    pid=child.pid,
                    memory_percentage_avg=memory_percent,
                    rss_bytes_avg=memory_rss,
                    vms_bytes_avg=memory_vms,
                    read_count=read_count,
                    write_count=write_count,
                    read_bytes=read_bytes,
                    write_bytes=write_bytes,
                )
            children_stats_list.append(child_stats)
        success_queue.put(True)

    except Exception as e:
        success_queue.put(False)
        stats = Stats()
        print(f"Error getting initial snapshot data: {e}")
    finally:
        data_to_substract_queue.put((stats, children_stats_list))


def get_process_by_pid(pid: int, refresh_rate: float) -> psutil.Process:
    """
    Retrieves a `psutil.Process` object by its process ID (PID).

    Args:
        pid (int): The process ID of the target process.
        refresh_rate (float): The time interval (in seconds) between each check for the existence of the process.

    Returns:
        psutil.Process: The `psutil.Process` object representing the process with the given PID.

    Raises:
        psutil.NoSuchProcess: If the process with the given PID does not exist within the specified timeout period.

    """
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
        None: This function does not return anything. It sends the CPU, memory, and I/O usage data to the passed queue in form of a Stats object.
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
        children_stats_list: List[Stats] = []
        children_data = {}

        while True:
            total_cpu, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(p, refresh_rate)

            cpu_usage_list.append(total_cpu)
            memory_rss_list.append(memory_rss)
            memory_vms_list.append(memory_vms)
            memory_percent_list.append(memory_percent)
            if look_for_children:
                for child in p.children(recursive=True):
                    if child.pid == os.getpid():
                        continue
                    total_cpu, memory_rss, memory_vms, memory_percent = get_total_cpu_memory(child, refresh_rate)
                    # TODO for each children we need to store this values and then create the stats object

                    children_data[child.pid] = {
                        "total_cpu": total_cpu,
                        "memory_rss": memory_rss,
                        "memory_vms": memory_vms,
                        "memory_percent": memory_percent,
                    }
            if (not finished_queue.empty() and finished_queue.get()) or not p.is_running():
                read_count, write_count, read_bytes, write_bytes = get_io_counters(p)

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


def get_total_cpu_memory(p: psutil.Process, refresh_rate: float) -> Tuple[float, int, int, float]:
    """
    Retrieves the total CPU usage, total RSS memory, total VMS memory, and memory percentage of a given process.

    Args:
        p (psutil.Process): The process object to retrieve the information from.
        refresh_rate (float): The interval in seconds between each CPU and memory usage measurement.

    Returns:
        Tuple[float, int, int, float]: A tuple containing the total CPU usage (float), total RSS memory (int), total VMS memory (int), and memory percentage (float).

    Note:
        - If the process do not exist or access is denied, the function returns (0.0, 0, 0, 0.0).
    """
    try:
        total_cpu = p.cpu_percent(interval=refresh_rate)
        memory_info = p.as_dict(attrs=["memory_info", "memory_percent"])

        # Extract the values
        memory_percent = memory_info["memory_percent"]
        total_rss = memory_info["memory_info"].rss
        total_vms = memory_info["memory_info"].vms
        return total_cpu, total_rss, total_vms, memory_percent
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0, 0, 0, 0.0


def get_io_counters(process: psutil.Process) -> Tuple[int, int, int, int]:
    """
    Retrieves the I/O counters of a given process and its children.

    Args:
        process (psutil.Process): The process object to retrieve the I/O counters from.

    Returns:
        Tuple[int, int, int, int]: A tuple containing the read count, write count, read bytes, and write bytes.

    Note:
        - If the process do not exist or access is denied, the function returns (0, 0, 0, 0).
        - If the platform is macOS, the function returns (0, 0, 0, 0).
        - If an exception occurs during the retrieval of the I/O counters, the function returns (0, 0, 0, 0).
    """
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
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
    return read_count, write_count, read_bytes, write_bytes
