"""jsonlproc — streaming JSON Lines processor.

Exposes the public API for use as a library.
"""
from .stream import JsonlStream
from .filter_engine import FilterEngine
from .projector import Projector
from .aggregator import Aggregator
from .sorter import Sorter
from .exceptions import (
    JsonlProcError,
    ParseError,
    FieldError,
    AggregationError,
)

__all__ = [
    "JsonlStream",
    "FilterEngine",
    "Projector",
    "Aggregator",
    "Sorter",
    "JsonlProcError",
    "ParseError",
    "FieldError",
    "AggregationError",
]

__version__ = "0.1.0"
