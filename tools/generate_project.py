"""Generate one fresh, headless contract-first OOP project from this template.

    python -B tools/generate_project.py --dest <missing-or-empty-dir> --slug <project-slug>

The output copies the existing contracts, SQLite and in-memory implementations
and shared behavior tests listed in ``generator/headless-oop/manifest.json``,
adds a thin CLI and composition root, initializes a new Git repository and
creates a fresh project identity through ``scripts/project_authority.py``.
No approval package, owner decision, runtime state or key is copied; the new
project stays unapproved. ``GENERATION.json`` records the template commit and
the SHA-256 of every generated file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import project_authority as authority  # noqa: E402

TEMPLATE = ROOT / "generator" / "headless-oop"
RECORD = "GENERATION.json"
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
# Paths the generator must never write: identity/approval are created only by
# the authority lifecycle, and Git metadata only by ``git init``.
RESERVED = ("config", ".git", RECORD)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _relative(value: object) -> PurePosixPath:
    _require(isinstance(value, str) and value != "", "Manifest path must be a string")
    path = PurePosixPath(value)
    _require(
        "\\" not in value
        and not path.is_absolute()
        and ":" not in value
        and all(part not in ("", ".", "..") for part in path.parts),
        f"Manifest path must be relative and normalized: {value!r}",
    )
    return path


def load_manifest(template: Path = TEMPLATE) -> list[tuple[str, Path, str]]:
    """Return ``(kind, source file, output path)`` for every manifest entry."""
    manifest = json.loads((template / "manifest.json").read_text(encoding="utf-8"))
    _require(
        set(manifest) == {"schema_version", "description", "copy", "assets"}
        and manifest["schema_version"] == "headless-oop-manifest/1",
        "Unsupported generator manifest",
    )
    entries = []
    for kind, base in (("copy", ROOT), ("asset", template)):
        for entry in manifest["copy" if kind == "copy" else "assets"]:
            _require(
                set(entry) == {"from", "to"}, "Manifest entry needs exactly from/to"
            )
            source = base / _relative(entry["from"])
            target = _relative(entry["to"])
            _require(
                target.parts[0] not in RESERVED,
                f"Manifest may not write reserved path {entry['to']}",
            )
            _require(
                source.is_file() and not source.is_symlink(),
                f"Manifest source is not a regular file: {entry['from']}",
            )
            entries.append((kind, source, target.as_posix()))
    targets = [target for _, _, target in entries]
    _require(len(targets) == len(set(targets)), "Manifest writes one path twice")
    return entries


def _empty_destination(dest: Path) -> Path:
    dest = Path(dest).absolute()
    _require(
        dest.resolve() != ROOT and ROOT not in dest.resolve().parents,
        "Destination must be outside the template checkout",
    )
    if os.path.lexists(dest):
        _require(
            dest.is_dir() and not dest.is_symlink(),
            "Destination exists and is not a plain directory",
        )
        _require(
            not any(dest.iterdir()), "Destination is not empty; refusing to generate"
        )
    else:
        dest.mkdir(parents=True)
    return dest.resolve()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _template_identity(entries: list[tuple[str, Path, str]]) -> dict:
    sources = sorted({source.relative_to(ROOT).as_posix() for _, source, _ in entries})
    changed = _git(
        ROOT, "status", "--porcelain", "--untracked-files=all", "--", *sources
    )
    return {
        "commit": _git(ROOT, "rev-parse", "HEAD"),
        "uncommitted_sources": sorted(line[3:] for line in changed.splitlines()),
    }


def generate(dest: Path, slug: str) -> dict:
    """Create the project in ``dest`` and return its generation record."""
    _require(
        isinstance(slug, str) and len(slug) <= 64 and SLUG.fullmatch(slug) is not None,
        "Project slug must be lowercase words separated by hyphens (maximum 64 characters)",
    )
    entries = load_manifest()
    template = _template_identity(entries)
    dest = _empty_destination(dest)
    _git(dest, "init", "-q", "-b", "main")

    files = {}
    for kind, source, target in entries:
        data = source.read_bytes()
        output = dest / target
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(data)
        files[target] = {
            "kind": kind,
            "source": source.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    project = authority.initialize(dest, slug)
    record = {
        "schema_version": "headless-oop-generation/1",
        "template": template,
        "project": project,
        "files": dict(sorted(files.items())),
    }
    with (dest / RECORD).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dest", type=Path, required=True, help="missing or empty directory"
    )
    parser.add_argument(
        "--slug", required=True, help="lowercase-hyphenated project name"
    )
    args = parser.parse_args(argv)
    try:
        record = generate(args.dest, args.slug)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as exc:
        detail = (
            exc.stderr.strip()
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        print(
            f"GENERATION REFUSED: {detail}\n"
            "Any partial output is left in place for inspection; nothing is deleted.",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "destination": str(Path(args.dest).resolve()),
                "project": record["project"],
                "state": "AWAITING_APPROVAL",
                "files": len(record["files"]),
                "next": [
                    "python main.py --mock process demo demo1234 1 2 3 10",
                    "python -m pytest",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
