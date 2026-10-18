"""Trusted shell facade. Importing it performs no work or provider access.

Shells depend on contracts.operator and this factory only. CLI tests should
inject an OperatorService into main(argv=None, *, service=None), so inspection
tests can prove that status and bare resume never invoke a paid operation.
"""

from pathlib import Path

from contracts.operator import OperatorService


def open_service(root: Path | None = None) -> OperatorService:
    from scripts.pilot_controller import Operator

    return Operator(root or Path(__file__).resolve().parents[1])
