"""Contract: numeric data processing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from contracts.auth import Session
from contracts.errors import AppError


# --------------------------------------------------------------------------- #
# Data contracts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProcessingResult:
    """Summary statistics for one batch of numeric input."""

    record_id: int
    count: int
    total: float
    mean: float
    minimum: float
    maximum: float
    created_at: datetime


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class ProcessingError(AppError):
    """Base class for data-processing failures."""


class EmptyInputError(ProcessingError):
    """``process`` was called with no values."""


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #


class DataProcessor(ABC):
    """Computes statistics over numeric batches and records the results."""

    @abstractmethod
    def process(self, values: Sequence[float], session: Session) -> ProcessingResult:
        """Summarise ``values`` and persist the result on behalf of ``session``.

        Args:
            values: Already parsed to floats by the caller. May be any length.
            session: The caller's session. Implementations must reject a
                session that the authenticator no longer recognises.

        Raises:
            EmptyInputError: ``values`` is empty.
            SessionExpiredError: ``session`` is not valid.
            StorageError: The result could not be persisted.
        """

    @abstractmethod
    def history(self, session: Session, limit: int = 10) -> list[ProcessingResult]:
        """Return up to ``limit`` most-recent results for the session's user,
        newest first.

        Raises:
            SessionExpiredError: ``session`` is not valid.
            StorageError: The store could not be read.
        """
