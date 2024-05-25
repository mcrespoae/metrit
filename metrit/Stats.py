from sys import platform

from .utils import format_size


class Stats:
    def __init__(
        self,
        cpu_percentage_max: float = 0.0,
        cpu_percentage_avg: float = 0.0,
        memory_percentage_avg: float = 0.0,
        rss_bytes_avg: float = 0.0,
        rss_bytes_max: int = 0,
        vms_bytes_avg: float = 0.0,
        vms_bytes_max: int = 0,
        write_count: int = 0,
        read_count: int = 0,
        write_bytes: int = 0,
        read_bytes: int = 0,
    ):
        self.cpu_percentage_avg: float = cpu_percentage_avg
        self.cpu_percentage_max: float = cpu_percentage_max
        self.memory_percentage_avg: float = memory_percentage_avg
        self.rss_bytes_avg: float = rss_bytes_avg
        self.rss_bytes_max: int = rss_bytes_max
        self.vms_bytes_avg: float = vms_bytes_avg
        self.vms_bytes_max: int = vms_bytes_max
        self.write_count: int = write_count
        self.read_count: int = read_count
        self.write_bytes: int = write_bytes
        self.read_bytes: int = read_bytes
        self.stats_reads: int = 1

    @staticmethod
    def get_non_negative_difference(value1, value2):
        """
        Calculates the non-negative difference between two values.

        Args:
            value1 (int or float): The first value.
            value2 (int or float): The second value.

        Returns:
            float: The non-negative difference between value1 and value2.
        """
        return max(value1 - value2, 0)

    def __sub__(self, other):
        """
        Subtracts the values of another `Stats` object from the current object and returns a new `Stats` object with the differences.

        Parameters:
            other (Stats): The `Stats` object to subtract from the current object.

        Returns:
            Stats: A new `Stats` object with the differences between the current object and the other object.
        """
        cpu_percentage_avg = self.get_non_negative_difference(self.cpu_percentage_avg, other.cpu_percentage_avg)
        cpu_percentage_max = self.get_non_negative_difference(self.cpu_percentage_max, other.cpu_percentage_max)
        memory_percentage_avg = self.get_non_negative_difference(
            self.memory_percentage_avg, other.memory_percentage_avg
        )
        rss_bytes_avg = self.get_non_negative_difference(self.rss_bytes_avg, other.rss_bytes_avg)
        rss_bytes_max = self.get_non_negative_difference(self.rss_bytes_max, other.rss_bytes_max)
        vms_bytes_avg = self.get_non_negative_difference(self.vms_bytes_avg, other.vms_bytes_avg)
        vms_bytes_max = self.get_non_negative_difference(self.vms_bytes_max, other.vms_bytes_max)
        write_count = self.get_non_negative_difference(self.write_count, other.write_count)
        read_count = self.get_non_negative_difference(self.read_count, other.read_count)
        write_bytes = self.get_non_negative_difference(self.write_bytes, other.write_bytes)
        read_bytes = self.get_non_negative_difference(self.read_bytes, other.read_bytes)

        return Stats(
            cpu_percentage_max=cpu_percentage_max,
            cpu_percentage_avg=cpu_percentage_avg,
            memory_percentage_avg=memory_percentage_avg,
            rss_bytes_avg=rss_bytes_avg,
            rss_bytes_max=rss_bytes_max,
            vms_bytes_avg=vms_bytes_avg,
            vms_bytes_max=vms_bytes_max,
            write_count=write_count,
            read_count=read_count,
            write_bytes=write_bytes,
            read_bytes=read_bytes,
        )

    def print(self, verbose, func_name, args, kwargs) -> None:
        """
        Prints the metrit data for a given function.

        Parameters:
            verbose (bool): If True, prints detailed information about the metrit data. If False, prints a concise summary.
            func_name (str): The name of the function.
            args (tuple): The positional arguments passed to the function.
            kwargs (dict): The keyword arguments passed to the function.

        Returns:
            None
        """

        if verbose:
            print("*" * 5, f"metrit data for function {func_name}:", "*" * 5)
            print(f"\tArgs: {args}.")
            print(f"\tKwargs: {kwargs}.")
            print(f"Maximum CPU usage: {self.cpu_percentage_max:.2f}%.")
            print(f"Average CPU usage: {self.cpu_percentage_avg:.2f}%.")
            print(f"Average memory usage: {self.memory_percentage_avg:.2f}%.")
            print(f"Maximum RSS memory usage: {format_size(self.rss_bytes_max)}.")
            print(f"Average RSS memory usage: {format_size(self.rss_bytes_avg)}.")
            print(f"Maximum VMS memory usage: {format_size(self.vms_bytes_max)}.")
            print(f"Average VMS memory usage: {format_size(self.vms_bytes_avg)}.")

            if platform != "darwin":
                print(f"IO read count: {self.read_count}.")
                print(f"IO bytes: {format_size(self.read_bytes)}.")
                print(f"IO writes count: {self.write_count}.")
                print(f"IO bytes: {format_size(self.write_bytes)}.")
            print("*" * 5, "End of metrit data.", "*" * 5)
        else:
            func_name_spacing = 30
            func_name = f"'{func_name}'"
            if len(func_name) > func_name_spacing:
                func_name = func_name[: func_name_spacing - 4] + "..." + "'"
            if platform != "darwin":
                output_format = "Function {:30} {:>8} avg of memory {:>8.2f}% avg of CPU {:>8} IO reads {:>8} IO writes"
                output = output_format.format(
                    func_name,
                    format_size(self.rss_bytes_avg),
                    self.cpu_percentage_avg,
                    format_size(self.read_bytes),
                    format_size(self.write_bytes),
                )
            else:
                output_format = "Function {:30} {:>8} avg of memory {:>8.2f}% avg of CPU"
                output = output_format.format(func_name, format_size(self.rss_bytes_avg), self.cpu_percentage_avg)
            print(output)
