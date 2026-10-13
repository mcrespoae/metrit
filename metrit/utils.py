import threading
from typing import Any, Callable, Dict, Tuple


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
            if unit == "B":
                return f"{bytes_size:.0f}{unit}"
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f}PB"  # If it exceeds TB, convert to petabytes


def extract_callable_and_args_if_method(func: Callable, *args: Any) -> Tuple[Callable, Tuple, Tuple, bool]:
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
    return callable_func, args, args_to_print, is_method


def function_key(func: Callable) -> Tuple[str, str, bytes]:
    """
    Builds a process-independent identity for a callable.

    The key must be identical in the parent process and in an isolated (spawned)
    child process. Therefore it is derived only from data that survives pickling
    and is not affected by per-process hash randomization:

        - the module name, with ``__mp_main__`` normalized to ``__main__`` (spawn
          imports the entry script under a different name in the child);
        - the qualified name;
        - the raw ``co_code`` bytecode.

    The ``co_code`` bytes are stored as-is and compared by equality (never by their
    ``hash()``, which is randomized per process).
    """
    raw = getattr(func, "__func__", func)  # unwrap classmethod/staticmethod
    code = getattr(raw, "__code__", None)
    module = getattr(raw, "__module__", "") or ""
    if module == "__mp_main__":
        module = "__main__"
    qualname = getattr(raw, "__qualname__", getattr(raw, "__name__", "")) or ""
    return module, qualname, code.co_code if code is not None else b""


class RecursionState:
    """
    Tracks, per thread, how many times each function is currently executing.

    A function is considered recursive when a call with the same key is already
    active on the current thread, which is what allows metrit to skip monitoring
    and avoid re-isolating nested calls. State is thread-local so concurrent calls
    from different threads never interfere with each other.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _active(self) -> Dict[Tuple[str, str, bytes], int]:
        active = getattr(self._local, "active", None)
        if active is None:
            active = {}
            self._local.active = active
        return active

    def is_recursive(self, key: Tuple[str, str, bytes]) -> bool:
        """Whether a call with the same key is already executing on this thread."""
        return self._active().get(key, 0) > 0

    def enter(self, key: Tuple[str, str, bytes]) -> None:
        active = self._active()
        active[key] = active.get(key, 0) + 1

    def exit(self, key: Tuple[str, str, bytes]) -> None:
        active = self._active()
        remaining = active.get(key, 0) - 1
        if remaining > 0:
            active[key] = remaining
        else:
            active.pop(key, None)


# One RecursionState per decorated function, keyed by function identity. The
# registry lets an isolated child process find the state of the function it is
# about to run (it re-imports the module and rebuilds the registry with the same
# keys) so nested calls are correctly detected as recursion there too.
_RECURSION_STATES: Dict[Tuple[str, str, bytes], RecursionState] = {}
_RECURSION_STATES_LOCK = threading.Lock()


def get_recursion_state(key: Tuple[str, str, bytes]) -> RecursionState:
    state = _RECURSION_STATES.get(key)
    if state is None:
        with _RECURSION_STATES_LOCK:
            state = _RECURSION_STATES.get(key)
            if state is None:
                state = RecursionState()
                _RECURSION_STATES[key] = state
    return state
