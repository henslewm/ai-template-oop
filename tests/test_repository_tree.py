"""Repository inventory includes client metadata without exposing worker paths."""

from pathlib import Path
import subprocess

import pytest

from scripts import workflow_closeout as closeout


ROOT = Path(__file__).resolve().parents[1]
CODEX_FILES = (
    ".codex/config.toml",
    ".codex/agents/operator.toml",
    ".codex/agents/researcher.toml",
    ".codex/agents/reviewer.toml",
)


def _git(root, *args, data=None):
    return subprocess.run(
        [
            "git", "-C", str(root),
            "-c", "user.name=Inventory fixture",
            "-c", "user.email=inventory@example.invalid",
            *args,
        ],
        input=data, text=True, capture_output=True, check=True,
    ).stdout.strip()


def test_fresh_clone_inventories_agents_but_keeps_them_out_of_worker_scope(tmp_path):
    root = tmp_path / "fresh clone"
    _git(ROOT, "clone", "--no-hardlinks", "--quiet", "--single-branch", str(ROOT), str(root))
    commit = _git(root, "rev-parse", "HEAD")

    inventory = closeout.tree(root, commit)

    assert set(inventory) == set(_git(root, "ls-files").splitlines())
    for name in CODEX_FILES:
        assert (root / name).is_file()
        assert inventory[name] == ("100644", _git(root, "rev-parse", commit + ":" + name))
        with pytest.raises(ValueError, match="Unsafe scope path"):
            closeout.a.h.checked_path(name)


@pytest.mark.parametrize("name", [
    ".codex/.aws/credentials",
    ".codex/nested/.codex/config.toml",
    "nested/.codex/config.toml",
])
def test_inventory_still_refuses_protected_descendants_and_nested_codex(tmp_path, name):
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--quiet", "-b", "feature/inventory")
    target = root / name
    target.parent.mkdir(parents=True)
    target.write_text("synthetic fixture\n", encoding="utf-8")
    _git(root, "add", "--force", ".")
    _git(root, "commit", "--quiet", "-m", "Protected-path fixture")

    with pytest.raises(ValueError, match="Unsafe scope path"):
        closeout.tree(root, _git(root, "rev-parse", "HEAD"))


def test_inventory_refuses_linked_codex_metadata(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--quiet", "-b", "feature/inventory")
    blob = _git(root, "hash-object", "-w", "--stdin", data="../outside\n")
    _git(root, "update-index", "--add", "--cacheinfo", "120000," + blob + ",.codex/config.toml")
    commit = _git(root, "commit-tree", _git(root, "write-tree"), "-m", "Linked metadata fixture")

    with pytest.raises(ValueError, match="Linked or non-file candidate tree"):
        closeout.tree(root, commit)
