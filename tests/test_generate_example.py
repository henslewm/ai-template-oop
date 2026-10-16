"""Generate real headless projects without running workers or altering the template app."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import project_authority
from tools.generate_example import generate

ROOT = Path(__file__).resolve().parents[1]


def run(root, *args):
    environment = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
    )
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-B", *args],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=45,
    )


@pytest.fixture
def isolated_host(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "host state"))
    return tmp_path


@pytest.fixture
def generated(isolated_host):
    root = isolated_host / "generated project with spaces"
    generate(root, "generated-example")
    return root


def test_generated_records_are_fresh_and_no_template_authority_is_copied(generated):
    identity = project_authority.identity(generated)
    assert identity["slug"] == "generated-example"
    assert project_authority.status(generated)["state"] == "AWAITING_APPROVAL"
    directory, _ = project_authority._location(generated)
    assert not (directory / "decisions.json").exists()
    assert not (directory.parent / "control.sqlite3").exists()
    for path in (
        "src/ui",
        "config/workflow-bootstrap.json",
        "config/project-approval.json",
        "scripts/pilot_controller.py",
        "scripts/openai_transport.py",
        ".env",
    ):
        assert not (generated / path).exists(), path
    assert (
        subprocess.check_output(["git", "-C", str(generated), "remote"]).strip() == b""
    )
    metadata = json.loads((generated / "GENERATION.json").read_text())
    assert metadata["project"] == identity
    assert len(metadata["template_commit"]) == 40
    assert isinstance(metadata["template_dirty"], bool)
    for item in metadata["files"]:
        assert (
            hashlib.sha256((generated / item["destination"]).read_bytes()).hexdigest()
            == item["output_sha256"]
        )
        assert (
            hashlib.sha256((ROOT / item["source"]).read_bytes()).hexdigest()
            == item["source_sha256"]
        )
    for path in (
        "contracts/auth.py",
        "contracts/data.py",
        "contracts/errors.py",
        "src/features/auth.py",
        "src/features/data.py",
        "tests/test_contract_auth.py",
        "tests/test_contract_data.py",
    ):
        assert (generated / path).read_bytes() == (ROOT / path).read_bytes()
    assert (generated / "src/testing/fakes.py").read_bytes() == (
        ROOT / "src/ui/mocks.py"
    ).read_bytes()


def test_two_projects_get_different_ids_and_empty_directory_is_supported(isolated_host):
    first = generate(isolated_host / "one", "one")
    second_path = isolated_host / "two"
    second_path.mkdir()
    second = generate(second_path, "two")
    assert first["project"]["id"] != second["project"]["id"]


def test_existing_work_is_never_overwritten(isolated_host):
    root = isolated_host / "existing"
    root.mkdir()
    marker = root / "keep.txt"
    marker.write_bytes(b"user work")
    with pytest.raises(ValueError, match="missing or empty"):
        generate(root)
    assert list(root.iterdir()) == [marker] and marker.read_bytes() == b"user work"
    assert not (isolated_host / "host state").exists()


@pytest.mark.parametrize("slug", ["../escape", "Two Words", "", "x" * 65])
def test_invalid_identity_does_not_create_output(isolated_host, slug):
    output = isolated_host / "output"
    with pytest.raises(ValueError):
        generate(output, slug)
    assert not output.exists()


def test_nested_template_output_is_refused():
    output = ROOT / "never-generate-inside-template"
    with pytest.raises(ValueError, match="outside the template"):
        generate(output)
    assert not output.exists()


@pytest.mark.parametrize(
    "original",
    [
        "../outside",
        ".ENV",
        ".Git/config",
        "config/Workflow-Bootstrap.json",
        "data.SQLITE3",
    ],
)
def test_manifest_cannot_copy_secrets_state_or_approval(isolated_host, original):
    source = isolated_host / "source"
    manifest = source / "templates/oop-example/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "oop-example/1",
                "copy": {"copy.txt": original},
                "render": {},
                "rewrites": {},
            }
        )
    )
    output = isolated_host / "output"
    with pytest.raises(ValueError):
        generate(output, source=source)
    assert not output.exists()


def test_rewrite_source_drift_is_refused_before_creating_output(isolated_host):
    source = isolated_host / "source"
    manifest = source / "templates/oop-example/manifest.json"
    manifest.parent.mkdir(parents=True)
    (source / "fixture.py").write_text("VALUE = 1\n")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "oop-example/1",
                "copy": {"tests/conftest.py": "fixture.py"},
                "render": {},
                "rewrites": {"tests/conftest.py": [["missing literal", "replacement"]]},
            }
        )
    )
    output = isolated_host / "output"
    with pytest.raises(ValueError, match="Source drift"):
        generate(output, source=source)
    assert not output.exists()


def test_generated_shared_real_mock_suite_runs_without_tk(generated):
    code = """
import importlib.abc, sys
class NoTk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'tkinter' or fullname.startswith('tkinter.'):
            raise AssertionError('Generated headless project imported Tk')
sys.meta_path.insert(0, NoTk())
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '-o', 'addopts=']))
"""
    result = run(generated, "-c", code)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "53 passed" in result.stdout


def test_boundary_check_refuses_presentation_importing_implementation(generated):
    cli = generated / "src/presentation/cli.py"
    cli.write_text(
        cli.read_text() + "\nfrom src.features.auth import ProductionAuthenticator\n"
    )
    result = run(generated, "tools/validate_boundaries.py")
    assert result.returncode == 1
    assert "src/presentation may not import src.features" in result.stdout


def test_copied_identity_lifecycle_can_prepare_a_review_without_activation(generated):
    result = run(generated, "tools/project_admin.py", "review")
    assert result.returncode == 0, result.stderr
    assert "fingerprint" in json.loads(result.stdout)
    status = run(generated, "tools/project_admin.py", "status")
    assert json.loads(status.stdout)["state"] == "AWAITING_APPROVAL"
    assert not (project_authority._location(generated)[0] / "decisions.json").exists()


def test_generator_cli_uses_its_own_root_from_another_directory(isolated_host):
    target = isolated_host / "cli output"
    result = run(
        isolated_host,
        str(ROOT / "tools/generate_example.py"),
        str(target),
        "--slug",
        "from-cli",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["project"]["slug"] == "from-cli"
    demo = run(target, "main.py", "--mock", "1", "2", "3")
    assert demo.returncode == 0, demo.stderr
    assert json.loads(demo.stdout)["total"] == 6
