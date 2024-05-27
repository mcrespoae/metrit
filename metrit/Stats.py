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
    cpu_percentage_max: float = 0.0
    cpu_percentage_avg: float = 0.0
    memory_percentage_avg: float = 0.0
    rss_bytes_avg: float = 0.0
    rss_bytes_max: int = 0
    vms_bytes_avg: float = 0.0
    vms_bytes_max: int = 0
    write_count: int = 0
    read_count: int = 0
    write_bytes: int = 0
    read_bytes: int = 0
