"""Static check that the layer boundaries are respected.

    python tools/validate_boundaries.py          # exit 1 on any violation

Rules (see README.md > Rules):
  contracts/      may import only the standard library (no I/O modules, no src.*)
  src/testing/    may not import src.features, src.container, or I/O modules
  src/features/   may not import src.testing, src.container, or UI toolkits;
                  every *public* class must subclass a contracts ABC
  src/container/  may import anything

This is an AST walk. Relative imports are resolved; dynamic imports
(``importlib``, ``__import__``) are not caught and remain a review criterion.
"""

from __future__ import annotations

import ast
import inspect
import sys
from abc import ABC
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules that do I/O. Importing one of these in an in-memory fake or a
# presentation layer means business logic has leaked out of the features.
IO_MODULES = (
    "sqlite3", "requests", "httpx", "aiohttp", "urllib", "http", "socket",
    "subprocess", "shutil", "smtplib", "ftplib", "pickle", "shelve",
)
UI_MODULES = ("tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "kivy")

# layer directory -> forbidden import prefixes
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "contracts": ("src", *IO_MODULES, *UI_MODULES),
    "src/testing": ("src.features", "src.container", *IO_MODULES, *UI_MODULES),
    "src/features": ("src.testing", "src.container", *UI_MODULES),
    "src/container": (),
}


def _layer_of(path: Path) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    for layer in sorted(FORBIDDEN, key=len, reverse=True):
        if rel == layer or rel.startswith(layer + "/"):
            return layer
    return None


def _package_parts(path: Path, root: Path) -> list[str]:
    """Dotted package the module in ``path`` belongs to, as a list."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    else:
        parts.pop()  # the module's own name
    return parts


def _imported_names(tree: ast.AST, path: Path, root: Path) -> list[tuple[int, str]]:
    """Yield (lineno, absolute dotted module name) for every import in ``tree``.

    Relative imports are resolved against the file's package so that
    ``from . import x`` inside ``src/testing/`` reports as ``src.testing.x``.
    """
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                pkg = _package_parts(path, root)
                pkg = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                base = ".".join(pkg + ([node.module] if node.module else []))
            if base:
                out.append((node.lineno, base))
            # ``from pkg import name`` may be importing a submodule; report it too.
            out.extend((node.lineno, f"{base}.{alias.name}" if base else alias.name) for alias in node.names)
    return out


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _contract_abcs() -> set[str]:
    """Names of every abstract class exported by ``contracts``."""
    sys.path.insert(0, str(ROOT))
    import contracts  # noqa: PLC0415  (deliberately late: ROOT must be on sys.path)

    names: set[str] = set()
    for name, obj in inspect.getmembers(contracts, inspect.isclass):
        if issubclass(obj, ABC) and getattr(obj, "__abstractmethods__", ()):
            names.add(name)
    return names


def _base_names(cls: ast.ClassDef) -> list[str]:
    names = []
    for base in cls.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _check_feature_classes(tree: ast.Module, abcs: set[str]) -> list[tuple[int, str]]:
    """Every public class must (transitively) subclass a contracts ABC."""
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    ok: set[str] = set()

    def implements(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in abcs or name in ok:
            return True
        node = classes.get(name)
        if node is None or name in seen:
            return False
        if any(implements(b, seen | {name}) for b in _base_names(node)):
            ok.add(name)
            return True
        return False

    problems = []
    for name, node in classes.items():
        if name.startswith("_"):
            continue
        if not implements(name):
            problems.append((node.lineno, f"public class {name} does not implement a contracts ABC"))
    return problems


def check(root: Path = ROOT) -> list[str]:
    abcs = _contract_abcs()
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        layer = _layer_of(path)
        if layer is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(root).as_posix()

        for lineno, module in _imported_names(tree, path, root):
            for prefix in FORBIDDEN[layer]:
                if _matches(module, prefix):
                    violations.append(f"{rel}:{lineno}: {layer} may not import {module}")

        if layer == "src/features":
            for lineno, msg in _check_feature_classes(tree, abcs):
                violations.append(f"{rel}:{lineno}: {msg}")
    return violations


def main() -> int:
    violations = check()
    for v in violations:
        print(v)
    if violations:
        print(f"\n{len(violations)} boundary violation(s).")
        return 1
    print("Boundaries OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
