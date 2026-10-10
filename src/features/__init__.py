"""The Workers: concrete implementations of the contracts.

Nothing in here knows about Tk, widgets, or display strings. Every public
class in this package subclasses a ``contracts`` ABC (enforced by
``tools/validate_boundaries.py``); private helpers may be anything.
"""

from src.features.auth import ProductionAuthenticator
from src.features.data import SQLDataProcessor

__all__ = ["ProductionAuthenticator", "SQLDataProcessor"]
