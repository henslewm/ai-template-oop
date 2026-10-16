"""Project identity and checkout-local offline approval, separate from campaign history.

No command grants provider, publication, merge or deployment authority. The host
operator and filesystem remain trusted; a typed decision is not authentication.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID, uuid4

from scripts import validate_workflow_approval as approval

IDENTITY = "config/project.json"
PACKAGE = "config/project-approval.json"
LOCAL = "project-authority"
POLICY = {
    "scope": "offline_workflow",
    "live_workers_enabled": False,
    "provider_egress": "none",
    "publication_authorized": False,
    "merge_authorized": False,
    "deployment_authorized": False,
    "task_api_budget_usd": 0,
    "project_api_budget_usd": 0,
}
TREES = ("scripts", "tools", "contracts", "runtime", "config")
ROOT_FILES = (
    "pyproject.toml",
    "CLAUDE.md",
    "PROMPTS.md",
    "BRANCH_RETENTION.md",
    "requirements-work-packets.txt",
    "tests/pilot_shell_checks.py",
)
require = approval.require


def digest(value: object) -> str:
    return hashlib.sha256(approval.canonical(value)).hexdigest()


def _no_links(path: Path) -> None:
    for part in (path, *path.parents):
        require(
            not part.is_symlink() and not getattr(part, "is_junction", lambda: False)(),
            "Linked project authority path refused",
        )
    if path.is_file():
        require(path.stat().st_nlink == 1, "Multiply linked authority file refused")


def project_root(root: Path) -> Path:
    root = Path(root).absolute()
    _no_links(root)
    root = root.resolve()
    actual = Path(approval.git(root, "rev-parse", "--show-toplevel").decode().strip())
    require(actual.resolve() == root, "Project root must be the Git worktree root")
    return root


def _location(root: Path) -> tuple[Path, str]:
    from scripts import workflow_state as ws

    root = project_root(root)
    common = Path(
        approval.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        .decode()
        .strip()
    ).resolve()
    identity = str(common).casefold() if os.name == "nt" else str(common)
    directory = ws.control_directory(root) / LOCAL
    _no_links(directory)
    return directory, identity


def applies(root: Path) -> bool:
    """Deleting the project record cannot restore legacy authority in this checkout."""
    directory, _ = _location(root)
    return any(
        os.path.lexists(path)
        for path in (
            Path(root) / IDENTITY,
            Path(root) / PACKAGE,
            directory / "identity.json",
        )
    )


def identity(root: Path) -> dict:
    _no_links(root / IDENTITY)
    value = approval.read_json(approval.safe_file(root, IDENTITY))
    approval.exact(value, {"schema_version", "id", "slug"}, "project identity")
    require(
        value["schema_version"] == "workflow-project/1", "Unsupported project identity"
    )
    require(isinstance(value["id"], str), "Invalid project UUID")
    require(str(UUID(value["id"])) == value["id"], "Invalid project UUID")
    require(
        isinstance(value["slug"], str)
        and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value["slug"]) is not None
        and len(value["slug"]) <= 64,
        "Project slug must be lowercase words separated by hyphens (maximum 64 characters)",
    )
    return value


def _read(path: Path) -> dict:
    _no_links(path)
    value = approval.read_json(path)
    require(isinstance(value, dict), "Authority record must be an object")
    return value


def _write(path: Path, value: dict, *, replace: bool = False) -> None:
    _no_links(path)
    data = approval.canonical(value) + b"\n"
    require(len(data) <= 4 * 1024 * 1024, "Authority record exceeds size limit")
    if not replace:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return
    # Mutations hold the checkout-wide exclusive lock; publish only complete JSON.
    descriptor, name = tempfile.mkstemp(prefix=".approval-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _no_links(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _locked(root: Path):
    directory, repository = _location(root)
    directory.mkdir(parents=True, exist_ok=True)
    _no_links(directory)
    lock = directory / "operation.lock"
    _no_links(lock)
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            "Project authority is busy or interrupted; inspect operation.lock"
        ) from exc
    try:
        os.close(descriptor)
        yield directory, repository
    finally:
        lock.unlink()


def _register(directory: Path, repository: str, project: dict) -> None:
    expected = {"project": project, "repository": repository}
    path = directory / "identity.json"
    if os.path.lexists(path):
        require(
            _read(path) == expected,
            "Registered project identity changed; no reset permitted",
        )
    else:
        _write(path, expected)


def initialize(root: Path, slug: str) -> dict:
    root = project_root(root)
    proposed = {
        "schema_version": "workflow-project/1",
        "id": str(uuid4()),
        "slug": slug,
    }
    # Validate before creating either project or host records.
    require(
        isinstance(slug, str)
        and len(slug) <= 64
        and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug) is not None,
        "Invalid project slug",
    )
    _no_links(root / IDENTITY)
    with _locked(root) as (directory, repository):
        require(
            not os.path.lexists(root / IDENTITY),
            "Project identity already exists; never reinitialize",
        )
        require(
            not os.path.lexists(root / PACKAGE),
            "Existing project approval requires inspection",
        )
        require(
            not (directory / "identity.json").exists(),
            "Registered identity exists; never reinitialize",
        )
        require(
            not any(p.name != LOCAL for p in directory.parent.iterdir()),
            "Existing workflow state cannot be reinitialized as a new project",
        )
        (root / "config").mkdir(exist_ok=True)
        _register(directory, repository, proposed)
        _write(root / IDENTITY, proposed)
    return proposed


def inventory(root: Path) -> dict[str, str]:
    """Bind control code/config, including untracked inputs; application work stays unbound."""
    result = {}
    for tree in TREES:
        parent = root / tree
        if not os.path.lexists(parent):
            continue
        _no_links(parent)

        def fail(error):
            raise error

        for directory, folders, files in os.walk(
            parent, followlinks=False, onerror=fail
        ):
            for folder in folders:
                _no_links(Path(directory) / folder)
            folders[:] = [name for name in folders if name != "__pycache__"]
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                if relative == PACKAGE or path.suffix in {".pyc", ".pyo"}:
                    continue
                _no_links(path)
                result[relative] = approval.content_digest(
                    approval.safe_file(root, relative).read_bytes()
                )
    for relative in ROOT_FILES:
        if os.path.lexists(root / relative):
            _no_links(root / relative)
            result[relative] = approval.content_digest(
                approval.safe_file(root, relative).read_bytes()
            )
    require(
        {
            IDENTITY,
            "scripts/project_authority.py",
            "scripts/workflow_state.py",
            "tools/project_admin.py",
        }
        <= result.keys(),
        "Project approval implementation is incomplete",
    )
    return dict(sorted(result.items()))


def _package(root: Path) -> dict:
    return {
        "schema_version": "workflow-project-approval/1",
        "project": identity(root),
        "policy": dict(POLICY),
        "implementation": inventory(root),
    }


def _checked_package(root: Path) -> tuple[dict, str]:
    recorded = _read(root / PACKAGE)
    current = _package(root)
    require(
        approval.canonical(recorded) == approval.canonical(current),
        "Project approval package is stale; review the current implementation",
    )
    return current, digest(current)


def review(root: Path) -> str:
    """Explicitly prepare/refresh the review package; never approve or reset workflow state."""
    root = project_root(root)
    with _locked(root) as (directory, repository):
        project = identity(root)
        _register(directory, repository, project)
        package = _package(root)
        path = root / PACKAGE
        if os.path.lexists(path):
            old = _read(path)
            require(
                old.get("schema_version") == package["schema_version"]
                and old.get("project") == project,
                "Foreign project approval package refused",
            )
        _write(path, package, replace=path.exists())
    return digest(package)


def _decisions(directory: Path, repository: str, project: dict) -> dict:
    path = directory / "decisions.json"
    if not os.path.lexists(path):
        return {
            "schema_version": "workflow-project-decisions/1",
            "repository": repository,
            "project_id": project["id"],
            "events": [],
        }
    data = _read(path)
    approval.exact(
        data,
        {"schema_version", "repository", "project_id", "events"},
        "project decisions",
    )
    require(
        data["schema_version"] == "workflow-project-decisions/1"
        and data["repository"] == repository
        and data["project_id"] == project["id"],
        "Project approval belongs to a different checkout or project",
    )
    require(
        isinstance(data["events"], list) and 0 < len(data["events"]) <= 1000,
        "Invalid project approval history",
    )
    previous = None
    for event in data["events"]:
        approval.exact(
            event,
            {"action", "fingerprint", "owner", "at", "decision", "previous", "hash"},
            "approval event",
        )
        require(
            event["action"] in {"APPROVE", "REVOKE"}
            and approval.hex_digest(event["fingerprint"], 64)
            and approval.text(event["owner"])
            and isinstance(event["at"], str)
            and event["decision"] == event["action"] + " " + event["fingerprint"]
            and event["previous"] == previous
            and event["hash"]
            == digest({k: v for k, v in event.items() if k != "hash"}),
            "Invalid project approval event",
        )
        instant = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        require(
            instant.utcoffset() == timezone.utc.utcoffset(instant),
            "Approval time must be UTC",
        )
        previous = event["hash"]
    return data


def active_anchor(root: Path) -> str:
    root = project_root(root)
    package, fingerprint = _checked_package(root)
    directory, repository = _location(root)
    project = package["project"]
    require(
        _read(directory / "identity.json")
        == {"project": project, "repository": repository},
        "Registered project identity changed",
    )
    decisions = _decisions(directory, repository, project)["events"]
    require(bool(decisions), "Project is AWAITING_APPROVAL in this checkout")
    latest = decisions[-1]
    require(
        latest["action"] == "APPROVE" and latest["fingerprint"] == fingerprint,
        "Project approval is revoked or stale; explicit approval required",
    )
    return fingerprint


def decide(root: Path, owner: str, decision: str, *, revoke: bool = False) -> str:
    root = project_root(root)
    require(
        approval.text(owner) and len(owner) <= 128 and owner.isprintable(),
        "An identified owner is required",
    )
    with _locked(root) as (directory, repository):
        package, fingerprint = _checked_package(root)
        project = package["project"]
        action = "REVOKE" if revoke else "APPROVE"
        require(
            decision == action + " " + fingerprint,
            "Literal decision does not match the reviewed fingerprint",
        )
        _register(directory, repository, project)
        history = _decisions(directory, repository, project)
        require(
            len(history["events"]) < 1000,
            "Approval history limit reached; preserve and inspect it",
        )
        event = {
            "action": action,
            "fingerprint": fingerprint,
            "owner": owner,
            "at": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "previous": history["events"][-1]["hash"] if history["events"] else None,
        }
        event["hash"] = digest(event)
        history["events"].append(event)
        # Recheck the executing/config closure before publishing the receipt.
        require(_package(root) == package, "Project changed while recording approval")
        target = directory / "decisions.json"
        _write(target, history, replace=target.exists())
    return fingerprint


def status(root: Path) -> dict:
    """Inspect without registration, directories, journal initialization or paid work."""
    root = project_root(root)
    if not applies(root):
        return {"state": "UNINITIALIZED", "next_action": "init --slug <project-slug>"}
    project = identity(root)
    try:
        fingerprint = active_anchor(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "state": "AWAITING_APPROVAL",
            "project": project,
            "next_action": "Review and explicitly approve this checkout",
            "blocker": str(exc),
        }
    return {
        "state": "ACTIVE_OFFLINE",
        "project": project,
        "fingerprint": fingerprint,
        "policy": dict(POLICY),
    }
