import logging
from importlib.metadata import PackageNotFoundError, version

from .core import MetritConfig, metrit

# Library best practice: do not emit output unless the application configures
# logging. Diagnostics are sent through the "metrit" logger; the measured
# resource summary is still printed to stdout by design.
logging.getLogger("metrit").addHandler(logging.NullHandler())

try:
    __version__ = version("metrit")
except PackageNotFoundError:  # Running from a source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = ["metrit", "MetritConfig", "__version__"]
