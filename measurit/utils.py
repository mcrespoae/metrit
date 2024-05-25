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


def print_usage(
    func_name: str,
    args: tuple,
    kwargs: dict,
    cpu_usage_list: list[float],
    memory_rss_list: list[int],
    memory_vms_list: list[int],
    io_counters_read: int,
    io_counters_write: int,
    io_read_bytes: int,
    io_write_bytes: int,
    verbose: bool = False,
) -> None:
    """
    Print the usage statistics for a function.
    Args:
        func_name (str): The name of the function.
        args (tuple): The arguments passed to the function.
        kwargs (dict): The keyword arguments passed to the function.
        cpu_usage_list (list[float]): A list of CPU usage values.
        memory_rss_list (list[int]): A list of RSS memory usage values.
        memory_vms_list (list[int]): A list of VMS memory usage values.
        io_counters_read (int): The number of IO read operations.
        io_counters_write (int): The number of IO write operations.
        io_read_bytes (int): The number of bytes read.
        io_write_bytes (int): The number of bytes written.
        verbose (bool, optional): Whether to print verbose output. Defaults to False.
    Returns:
        None
    """
    if cpu_usage_list:
        cpu_max: float = max(cpu_usage_list)
        cpu_avg: float = sum(cpu_usage_list) / len(cpu_usage_list)

    else:
        cpu_max: float = float("-inf")
        cpu_avg: float = float("-inf")

    if memory_rss_list:
        rss_max: int = max(memory_rss_list)
        rss_avg: float = sum(memory_rss_list) / len(memory_rss_list)

    else:
        rss_max = 0
        rss_avg: float = float("-inf")

    if memory_vms_list:
        vms_max = max(memory_vms_list)
        vms_avg = sum(memory_vms_list) / len(memory_vms_list)
    else:
        vms_max = 0
        vms_avg: float = float("-inf")

    if verbose:
        print("*" * 5, f"measureit data for function {func_name}:", "*" * 5)
        print(f"\tArgs: {args}.")
        print(f"\tKwargs: {kwargs}.")
        print(f"Maximum CPU usage: {cpu_max:.2f}%.")
        print(f"Average CPU usage: {cpu_avg:.2f}%.")
        print(f"Maximum RSS memory usage: {format_size(rss_max)}.")
        print(f"Average RSS memory usage: {format_size(rss_avg)}.")
        print(f"Maximum VMS memory usage: {format_size(vms_max)}.")
        print(f"Average VMS memory usage: {format_size(vms_avg)}.")
        print(f"IO read count: {io_counters_read}.")
        print(f"IO bytes: {format_size(io_read_bytes)}.")
        print(f"IO writes count: {io_counters_write}.")
        print(f"IO bytes: {format_size(io_write_bytes)}.")
        print("*" * 5, "End of measureit data.", "*" * 5)
    else:
        func_name_spacing = 30
        func_name = f"'{func_name}'"
        if len(func_name) > func_name_spacing:
            func_name = func_name[: func_name_spacing - 4] + "..." + "'"
        output_format = "Function {:30} {:>8} avg of memory {:>8.2f}% avg of CPU {:>8} IO reads {:>8} IO writes"
        output = output_format.format(
            func_name, format_size(rss_avg), cpu_avg, format_size(io_read_bytes), format_size(io_write_bytes)
        )
        print(output)
