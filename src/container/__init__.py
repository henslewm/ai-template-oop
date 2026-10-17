"""The Wire-Up: the only package allowed to import both ``src.testing`` and
``src.features``. Builds concrete objects and injects them."""

from src.container.wiring import Services, build_mock, build_production

__all__ = ["Services", "build_mock", "build_production"]
