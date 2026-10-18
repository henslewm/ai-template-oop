"""Generate one headless OOP software example from an explicit source manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import project_authority
from scripts import validate_workflow_approval as approval

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "templates/oop-example/manifest.json"
OWNED_RECORDS = {
    "config/project.json",
    "config/project-approval.json",
    "GENERATION.json",
    ".generation.lock",
}
FORBIDDEN = {
    value.casefold() for value in {"config/workflow-bootstrap.json", *OWNED_RECORDS}
}
PROJECT_INPUTS = {
    "PROJECT_SPEC.json",
    "INTAKE_REVIEW.json",
    "PROJECT.md",
    "tests/test_project_acceptance.py",
}
PROFILE_FILES = {
    "synthetic-hardware-frame-parser/1": {
        "WORK_PACKET.json": "examples/work-packets/software-hardware.contract.json",
        "contracts/synthetic_frame.py": "templates/oop-example/assets/synthetic_frame_contract.py.tmpl",
        "src/features/synthetic_frame.py": "templates/oop-example/assets/synthetic_frame.py.tmpl",
        "src/testing/synthetic_frame.py": "templates/oop-example/assets/synthetic_frame_fake.py.tmpl",
        "tests/test_parse_synthetic_frame_contract.py": "templates/oop-example/assets/test_parse_synthetic_frame_contract.py.tmpl",
        "tests/test_hardware_profile.py": "templates/oop-example/assets/test_hardware_profile.py.tmpl",
    }
}
PROFILE_EXTENSIONS = {
    "synthetic-hardware-frame-parser/1": {
        "contracts/__init__.py": "templates/oop-example/assets/synthetic_contracts_exports.py.tmpl",
        "src/container/wiring.py": "templates/oop-example/assets/synthetic_wiring.py.tmpl",
    }
}


def _path(value: str) -> None:
    parts = approval.relative_path(value).parts
    approval.require(
        not any(
            p.casefold() in {".git", ".aws", ".codex", ".agents", ".env"}
            or p.casefold().startswith(".env.")
            for p in parts
        ),
        "Secrets are not generation inputs",
    )
    approval.require(
        Path(value).suffix.casefold() not in {".db", ".sqlite3", ".pyc"},
        "Runtime files are not generation inputs",
    )
    approval.require(
        value.casefold() not in FORBIDDEN, "Approval/runtime records cannot be copied"
    )


def _no_links(path: Path) -> None:
    for part in (path, *path.parents):
        approval.require(
            not part.is_symlink() and not getattr(part, "is_junction", lambda: False)(),
            "Linked generation destination refused",
        )


def _plan(
    source: Path, slug: str, profile: str | None = None
) -> tuple[dict[str, bytes], list[dict], str]:
    raw = approval.safe_file(source, MANIFEST).read_bytes()
    manifest = approval.read_json(source / MANIFEST)
    approval.exact(
        manifest,
        {"schema_version", "copy", "render", "rewrites"},
        "generation manifest",
    )
    approval.require(
        manifest["schema_version"] == "oop-example/1", "Unsupported generation manifest"
    )
    files, records, names = {}, [], set()
    for kind in ("copy", "render"):
        approval.require(
            isinstance(manifest[kind], dict), "Manifest mappings must be objects"
        )
        for destination, original in manifest[kind].items():
            _path(destination)
            _path(original)
            approval.require(
                destination.casefold() not in names, "Duplicate generated path"
            )
            names.add(destination.casefold())
            content = approval.safe_file(source, original).read_bytes()
            output = (
                content
                if kind == "copy"
                else content.decode("utf-8")
                .replace("@PROJECT_SLUG@", slug)
                .encode("utf-8")
            )
            files[destination] = output
            records.append(
                {
                    "source": original,
                    "destination": destination,
                    "kind": kind,
                    "source_sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    approval.require(
        isinstance(manifest["rewrites"], dict), "Manifest rewrites must be an object"
    )
    for destination, replacements in manifest["rewrites"].items():
        approval.require(
            destination in files and isinstance(replacements, list),
            "Rewrite needs a generated file",
        )
        text = files[destination].decode("utf-8").replace("\r\n", "\n")
        for pair in replacements:
            approval.require(
                isinstance(pair, list)
                and len(pair) == 2
                and all(isinstance(item, str) for item in pair),
                "Invalid literal rewrite",
            )
            old, new = pair
            approval.require(
                bool(old) and text.count(old) == 1,
                "Source drift: expected exactly one literal rewrite in " + destination,
            )
            text = text.replace(old, new, 1)
        files[destination] = text.encode("utf-8")
    for destination, original in PROFILE_FILES.get(profile, {}).items():
        _path(destination)
        _path(original)
        approval.require(
            destination.casefold() not in names, "Duplicate generated path"
        )
        names.add(destination.casefold())
        content = approval.safe_file(source, original).read_bytes()
        files[destination] = content
        records.append(
            {
                "source": original,
                "destination": destination,
                "kind": "profile",
                "source_sha256": hashlib.sha256(content).hexdigest(),
                "output_sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    for destination, original in PROFILE_EXTENSIONS.get(profile, {}).items():
        _path(destination)
        _path(original)
        approval.require(
            destination in files, "Profile extension needs a template file"
        )
        content = approval.safe_file(source, original).read_bytes()
        files[destination] += b"\n" + content
        record = next(item for item in records if item["destination"] == destination)
        record["extensions"] = [
            {
                "source": original,
                "source_sha256": hashlib.sha256(content).hexdigest(),
            }
        ]
    for record in records:
        record["output_sha256"] = hashlib.sha256(
            files[record["destination"]]
        ).hexdigest()
    return files, records, hashlib.sha256(raw).hexdigest()


def generate(
    destination: Path,
    slug: str = "oop-example",
    *,
    source: Path = ROOT,
    profile: str | None = None,
    project_files: dict[str, bytes] | None = None,
) -> dict:
    approval.require(
        isinstance(slug, str)
        and len(slug) <= 64
        and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug) is not None,
        "Use a lowercase project slug separated by hyphens",
    )
    source = Path(source).resolve()
    destination = Path(destination).absolute()
    _no_links(destination)
    destination = destination.resolve()
    approval.require(
        not destination.is_relative_to(source)
        and not source.is_relative_to(destination),
        "Generate outside the template checkout",
    )
    if destination.exists():
        approval.require(
            destination.is_dir() and not any(destination.iterdir()),
            "Destination must be missing or empty; existing work is never overwritten",
        )
    files, records, manifest_hash = _plan(source, slug, profile)
    for relative, content in (project_files or {}).items():
        approval.require(
            relative in PROJECT_INPUTS and isinstance(content, bytes),
            "Only fixed intake document/test paths may supplement the example",
        )
        approval.require(
            relative not in files, "Intake must not replace template files"
        )
        files[relative] = content
        records.append(
            {
                "source": None,
                "destination": relative,
                "kind": "intake",
                "source_sha256": hashlib.sha256(content).hexdigest(),
                "output_sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    revision = approval.git(source, "rev-parse", "HEAD").decode().strip()
    dirty = bool(
        approval.git(
            source, "status", "--porcelain", "--untracked-files=normal"
        ).strip()
    )
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / ".generation.lock"
    with lock.open("xb"):
        pass
    try:
        approval.require(
            list(destination.iterdir()) == [lock],
            "Destination changed during generation; inspect it",
        )
        for relative, content in files.items():
            path = destination / relative
            _no_links(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(content)
        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
                "--template=",
                "--initial-branch=feature/example",
                str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        project = project_authority.initialize(destination, slug)
        provenance = {
            "schema_version": "oop-example-generation/1",
            "template_commit": revision,
            "template_dirty": dirty,
            "manifest_sha256": manifest_hash,
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "project": project,
            "files": records,
        }
        with (destination / "GENERATION.json").open("x", encoding="utf-8") as output:
            json.dump(provenance, output, indent=2)
            output.write("\n")
        return {
            "directory": str(destination),
            "project": project,
            "workflow_state": "AWAITING_APPROVAL",
            "run": "python main.py --mock 1 2 3",
        }
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--slug", default="oop-example")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(generate(args.destination, args.slug), indent=2))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            "Generation held: "
            + (
                str(exc)
                if isinstance(exc, ValueError)
                else "Input/output failed; preserve any partial destination and choose a fresh directory"
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
