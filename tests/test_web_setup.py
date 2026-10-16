"""web_setup.py: one zip and one clipboard copy per web client, read from each client's own list."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import web_setup  # noqa: E402 -- existing scripts layout

EXPECTED_COUNTS = {"chatgpt": 14, "claude": 14, "mistral": 15}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of only the client docs and the files they list, so each run is small and isolated."""
    root = tmp_path / "project"
    names = {".web-setup/.gitignore"}
    for instructions, listing, _ in web_setup.CLIENTS.values():
        names |= {instructions, listing, *web_setup.listed_files(ROOT / listing)}
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, root / name)
    return root


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # An empty PATH leaves no clipboard tool, so the run is deterministic and touches no real clipboard.
    env = {**os.environ, "PYTHONUTF8": "1", "PATH": ""}
    return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/web_setup.py"), *args, "--root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)


def archive(root: Path, client: str) -> Path:
    return root / web_setup.OUTPUT / f"web-setup-{client}.zip"


@pytest.mark.parametrize("client", sorted(web_setup.CLIENTS))
def test_each_listed_file_exists_in_the_repository(client):
    _, listing, _ = web_setup.CLIENTS[client]
    names = web_setup.listed_files(ROOT / listing)
    assert len(names) == EXPECTED_COUNTS[client]
    assert len(set(names)) == len(names)
    assert [name for name in names if web_setup.inside(ROOT, name) is None] == []


@pytest.mark.parametrize("client", sorted(web_setup.CLIENTS))
def test_each_client_zip_holds_exactly_its_listed_files(project, client):
    _, listing, _ = web_setup.CLIENTS[client]
    names = web_setup.listed_files(ROOT / listing)
    result = run_cli(project, "--client", client)
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(archive(project, client)) as bundle:
        assert sorted(bundle.namelist()) == sorted(names)
        assert bundle.read("CLAUDE.md") == (ROOT / "CLAUDE.md").read_bytes()
    # No clipboard tool: the user is told which file to paste from.
    assert "Paste the contents of" in result.stdout
    assert f"({len(names)} files)" in result.stdout


def test_missing_listed_file_is_refused(project):
    (project / "BRANCH_RETENTION.md").unlink()
    result = run_cli(project, "--client", "chatgpt")
    assert result.returncode == 1
    assert "Web setup refused: missing BRANCH_RETENTION.md" in result.stdout
    assert not archive(project, "chatgpt").exists()


def test_missing_instructions_are_refused(project):
    (project / ".claude-web/PROJECT_INSTRUCTIONS.md").unlink()
    result = run_cli(project, "--client", "claude")
    assert result.returncode == 1
    assert "PROJECT_INSTRUCTIONS.md" in result.stdout
    assert not archive(project, "claude").exists()


def test_empty_list_is_refused(project):
    (project / ".mistral/PROJECT_KNOWLEDGE.md").write_text("# Nothing listed\n", encoding="utf-8")
    result = run_cli(project, "--client", "mistral")
    assert result.returncode == 1
    assert "no files listed in .mistral/PROJECT_KNOWLEDGE.md" in result.stdout


def test_paths_outside_the_project_are_refused(project, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("credential", encoding="utf-8")
    listing = project / ".chatgpt/PROJECT_FILES.md"
    original = listing.read_text(encoding="utf-8")
    for entry in (str(outside), "../secret.txt"):
        listing.write_text(original + f"\n15. `{entry}`\n", encoding="utf-8")
        result = run_cli(project, "--client", "chatgpt")
        assert result.returncode == 1, result.stdout
        assert "outside the project" in result.stdout
        assert not archive(project, "chatgpt").exists()


def test_symlinked_listed_file_is_refused(project, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("credential", encoding="utf-8")
    target = project / "README.md"
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this system")
    result = run_cli(project, "--client", "chatgpt")
    assert result.returncode == 1, result.stdout
    assert "README.md" in result.stdout
    assert not archive(project, "chatgpt").exists()


def test_symlinked_archive_destination_is_refused_and_target_untouched(project, tmp_path):
    outside = tmp_path / "important.txt"
    outside.write_text("keep me", encoding="utf-8")
    try:
        archive(project, "chatgpt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this system")
    result = run_cli(project, "--client", "chatgpt")
    assert result.returncode == 1, result.stdout
    assert "is a link" in result.stdout
    assert outside.read_text(encoding="utf-8") == "keep me"
    assert list((project / web_setup.OUTPUT).glob(".building-*")) == []


def test_output_folder_that_is_a_file_is_refused(project):
    output = project / web_setup.OUTPUT
    shutil.rmtree(output)
    output.write_text("not a folder", encoding="utf-8")
    result = run_cli(project, "--client", "claude")
    assert result.returncode == 1, result.stdout
    assert "not a directory" in result.stdout
    assert output.read_text(encoding="utf-8") == "not a folder"


def test_rerun_replaces_the_archive(project):
    assert run_cli(project, "--client", "claude").returncode == 0
    archive(project, "claude").write_bytes(b"stale")
    result = run_cli(project, "--client", "claude")
    assert result.returncode == 0, result.stdout
    assert zipfile.is_zipfile(archive(project, "claude"))
    assert list((project / web_setup.OUTPUT).glob(".building-*")) == []


def test_archives_are_ignored_by_git():
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    archives = [f"{web_setup.OUTPUT}/web-setup-{client}.zip" for client in sorted(web_setup.CLIENTS)]
    kept = f"{web_setup.OUTPUT}/.gitignore"
    # One call; -v names the deciding rule per path, and a "!" rule or no rule ("::") means not ignored.
    result = subprocess.run(["git", "check-ignore", "-v", "--non-matching", "--no-index", *archives, kept],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    rules = dict(reversed(line.split("\t", 1)) for line in result.stdout.splitlines())
    assert set(rules) == {*archives, kept}
    ignored = {path for path, rule in rules.items() if not rule.startswith("::") and ":!" not in rule}
    assert ignored == set(archives)


def test_clipboard_copy_uses_the_platform_tool():
    with mock.patch.object(web_setup.shutil, "which", return_value="tool"), \
            mock.patch.object(web_setup.subprocess, "run") as run:
        run.return_value.returncode = 0
        assert web_setup.copy_to_clipboard("instructions")
    sent = run.call_args.kwargs["input"]
    assert sent in ("instructions".encode("utf-16"), b"instructions")


def test_no_clipboard_tool_reports_false():
    with mock.patch.object(web_setup.shutil, "which", return_value=None):
        assert not web_setup.copy_to_clipboard("instructions")
