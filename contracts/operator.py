"""Compact operator contract shared with the bounded onboarding shell."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorView:
    objective: str
    progress: str
    settled_usd: float
    liability_usd: float
    failed_attempt_usd: float
    context_bytes: int
    accepted_changes: int
    cost_per_accepted_change_usd: float | None
    blockers: tuple[str, ...]
    next_action: str


class OperatorService(ABC):
    @abstractmethod
    def start(self, objective: str) -> OperatorView:
        """Run the one approved preset, or return its existing lifetime state."""

    @abstractmethod
    def status(self) -> OperatorView:
        """Read existing records only; never provision state or make model calls."""

    @abstractmethod
    def resume(self, *, run: bool = False) -> OperatorView:
        """Inspect by default; run=True explicitly continues eligible work."""
