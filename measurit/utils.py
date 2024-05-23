from typing import Dict, List, Tuple


def substract_data(
    memory_rss_to_substract: int,
    memory_rss_list: List[int],
    memory_vms_list_to_substract: int,
    memory_vms_list: List[int],
    io_data_to_substract: Dict[str, int],
    io_data: Dict[str, int],
) -> Tuple[List[int], List[int], Dict[str, int]]:

    cleaned_memory_rss_list: List[int] = [max(x - memory_rss_to_substract, 0) for x in memory_rss_list]
    cleaned_memory_vms_list: List[int] = [max(x - memory_vms_list_to_substract, 0) for x in memory_vms_list]
    cleaned_io_data: Dict[str, int] = {
        key: max(io_data[key] - io_data_to_substract[key], 0) for key in io_data if key in io_data_to_substract
    }

    return cleaned_memory_rss_list, cleaned_memory_vms_list, cleaned_io_data


def format_size(bytes_size: int | float) -> str:
    """Converts a size in bytes to a human-readable format."""
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
        print(
            f"Function '{func_name}' took: {format_size(rss_avg)} avg of memory, {cpu_avg:.2f}% avg of CPU, {format_size(io_read_bytes)} IO reads, {format_size(io_write_bytes)} IO writes."
        )
