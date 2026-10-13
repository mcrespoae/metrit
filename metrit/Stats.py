from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class RawStats:
    cpu_percent: List[float] = field(default_factory=list)
    memory_percent: List[float] = field(default_factory=list)
    rss_bytes: List[int] = field(default_factory=list)
    vms_bytes: List[int] = field(default_factory=list)
    io_read_count: int = 0
    io_write_count: int = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0


@dataclass(slots=True)
class Stats:
    """
    Aggregated measurements for a run.

    Memory semantics:
        - ``rss_bytes_max`` / ``vms_bytes_max`` are the **absolute peaks** observed while the
          function ran (max of the sampled totals).
        - ``rss_bytes_growth`` / ``vms_bytes_growth`` are the peaks minus the baseline peak,
          i.e. how much the function added on top of the pre-run snapshot.
        - ``rss_bytes_avg`` / ``vms_bytes_avg`` are the **mean absolute** values.
        - ``memory_percentage_*`` are relative to the total system RAM, also absolute.
    CPU is a sum across the measured processes (see ``find_children``) over the sampling window.
    """

    cpu_percentage_max: float = 0.0
    cpu_percentage_avg: float = 0.0
    memory_percentage_avg: float = 0.0
    memory_percentage_max: float = 0.0
    rss_bytes_avg: float = 0.0
    rss_bytes_max: int = 0
    rss_bytes_growth: int = 0
    vms_bytes_avg: float = 0.0
    vms_bytes_max: int = 0
    vms_bytes_growth: int = 0
    write_count: int = 0
    read_count: int = 0
    write_bytes: int = 0
    read_bytes: int = 0
