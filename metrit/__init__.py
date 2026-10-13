import logging

from .core import MetritConfig, metrit

# Library best practice: do not emit output unless the application configures
# logging. Diagnostics are sent through the "metrit" logger; the measured
# resource summary is still printed to stdout by design.
logging.getLogger("metrit").addHandler(logging.NullHandler())

__all__ = ["metrit", "MetritConfig"]
