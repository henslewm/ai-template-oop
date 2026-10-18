"""Intake review must produce a runnable project without inventing requirements."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts import project_authority
from tools import project_intake as intake
from tools.generate_example import generate as generate_example

ROOT = Path(__file__).resolve().parents[1]


def run(root, *args):
    env = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
    )
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-B", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "host"))
    return tmp_path


@pytest.fixture
def spec():
    value = intake.draft("requirements-example")
    value["purpose"] = (
        "Summarize fictional classroom measurements after authentication."
    )
    value["open_questions"] = []
    return copy.deepcopy(value)


def build(spec, path):
    return intake.generate(
        spec,
        path,
        accepted_fingerprint=intake.review(spec)["fingerprint"],
        reviewed_by="test-reviewer",
    )


def test_draft_needs_review_and_does_not_overwrite_existing_input(host):
    path = host / "spec.json"
    cli = str(ROOT / "tools/project_intake.py")
    result = run(host, cli, "draft", str(path), "--slug", "classroom")
    assert result.returncode == 0, result.stderr
    original = path.read_bytes()
    assert not intake.review(json.loads(original))["ready"]
    again = run(host, cli, "draft", str(path), "--slug", "other")
    assert again.returncode == 1
    assert path.read_bytes() == original


def test_open_questions_and_stale_review_hold_before_creating_output(host, spec):
    accepted = intake.review(spec)["fingerprint"]
    spec["open_questions"] = ["Is the expected mean correct?"]
    with pytest.raises(ValueError, match="open_questions"):
        intake.generate(
            spec, host / "questions", accepted_fingerprint=accepted, reviewed_by="owner"
        )
    spec["open_questions"] = []
    spec["purpose"] += " Changed after review."
    with pytest.raises(ValueError, match="fingerprint"):
        intake.generate(
            spec, host / "changed", accepted_fingerprint=accepted, reviewed_by="owner"
        )
    assert list(host.iterdir()) == []


def test_template_drift_changes_review_and_holds_generation(host, spec, monkeypatch):
    fingerprint = intake.review(spec)["fingerprint"]
    original = intake.example._plan

    def changed(*args):
        files, records, digest = original(*args)
        records[0]["source_sha256"] = "0" * 64
        return files, records, digest

    monkeypatch.setattr(intake.example, "_plan", changed)
    with pytest.raises(ValueError, match="fingerprint"):
        intake.generate(
            spec,
            host / "changed",
            accepted_fingerprint=fingerprint,
            reviewed_by="owner",
        )
    assert list(host.iterdir()) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "software-intake/2"),
        ("slug", "../escape"),
        ("purpose", " "),
        ("purpose", "hidden\x00instruction"),
        ("workflow", {"profile": "web-dashboard/1", "goal": "Build a website"}),
        ("features", [*intake.FEATURES, "email"]),
        ("contracts", ["InventedContract"]),
        ("dependencies", ["requests"]),
        ("open_questions", "none"),
        ("acceptance_criteria", []),
    ],
)
def test_unsupported_or_incomplete_requests_are_not_silently_generated(
    host, spec, field, value
):
    spec[field] = value
    with pytest.raises(ValueError):
        intake.generate(
            spec, host / "output", accepted_fingerprint="0" * 64, reviewed_by="owner"
        )
    assert list(host.iterdir()) == []


@pytest.mark.parametrize(
    "values", [[], [True], [float("inf")], [float("nan")], [1e10], ["1"], [10**400]]
)
def test_invalid_numeric_criteria_are_refused(spec, values):
    spec["acceptance_criteria"][0]["values"] = values
    with pytest.raises(ValueError):
        intake.validate(spec)


def test_closed_fields_and_duplicate_criteria_and_boolean_expectations(spec):
    extra = {**spec, "workers": ["launch-provider"]}
    with pytest.raises(ValueError, match="fields"):
        intake.validate(extra)
    spec["acceptance_criteria"] *= 2
    with pytest.raises(ValueError, match="unique"):
        intake.validate(spec)
    spec["acceptance_criteria"] = [spec["acceptance_criteria"][0]]
    spec["acceptance_criteria"][0]["expected"]["count"] = True
    with pytest.raises(ValueError, match="finite"):
        intake.validate(spec)


def test_missing_reviewer_and_existing_destination_are_held(host, spec):
    with pytest.raises(ValueError, match="reviewed_by"):
        intake.generate(
            spec,
            host / "empty-reviewer",
            accepted_fingerprint=intake.review(spec)["fingerprint"],
            reviewed_by=" ",
        )
    target = host / "existing"
    target.mkdir()
    (target / "user.txt").write_text("keep")
    with pytest.raises(ValueError, match="missing or empty"):
        build(spec, target)
    assert (target / "user.txt").read_text() == "keep"
    assert not (host / "host").exists()


@pytest.mark.parametrize(
    "path",
    ["../escape", "main.py", "config/project-approval.json", "PROJECT_SPEC.JSON"],
)
def test_generator_supplements_cannot_replace_code_or_authority(host, path):
    with pytest.raises(ValueError, match="fixed intake"):
        generate_example(host / "output", project_files={path: b"untrusted"})
    assert not (host / "output").exists()


def test_review_and_generation_work_from_foreign_cwd_and_run_full_project(host, spec):
    path = host / "request.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    cli = str(ROOT / "tools/project_intake.py")
    review = run(host, cli, "review", str(path))
    assert review.returncode == 0, review.stderr
    report = json.loads(review.stdout)
    assert report["ready"] and report["specification"] == spec
    assert "contracts/batch.py" in report["architecture"]
    target = host / "generated intake with spaces"
    generated = run(
        host,
        cli,
        "generate",
        str(path),
        str(target),
        "--accept",
        report["fingerprint"],
        "--reviewed-by",
        "fixture-owner",
    )
    assert generated.returncode == 0, generated.stderr
    assert json.loads((target / "PROJECT_SPEC.json").read_text()) == spec
    acknowledgment = json.loads((target / "INTAKE_REVIEW.json").read_text())
    assert acknowledgment["fingerprint"] == report["fingerprint"]
    assert acknowledgment["reviewed_by"] == "fixture-owner"
    assert project_authority.status(target)["state"] == "AWAITING_APPROVAL"
    assert not (target / "config/project-approval.json").exists()
    metadata = json.loads((target / "GENERATION.json").read_text())
    records = [item for item in metadata["files"] if item["kind"] == "intake"]
    assert {item["destination"] for item in records} == intake.example.PROJECT_INPUTS
    for item in records:
        assert item["source"] is None
        assert (
            hashlib.sha256((target / item["destination"]).read_bytes()).hexdigest()
            == item["output_sha256"]
        )
    result = run(
        target, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "55 passed" in result.stdout
    executed = run(target, "main.py", "--mock", "1", "2", "3")
    assert executed.returncode == 0 and json.loads(executed.stdout)["total"] == 6


def test_user_expected_outcomes_are_not_rewritten_to_make_tests_pass(host, spec):
    spec["acceptance_criteria"][0]["expected"]["total"] = 99
    target = host / "deliberate-mismatch"
    build(spec, target)
    result = run(
        target,
        "-m",
        "pytest",
        "tests/test_project_acceptance.py",
        "-o",
        "addopts=",
        "-q",
    )
    assert result.returncode == 1
    assert "2 failed" in result.stdout
    assert (
        json.loads((target / "PROJECT_SPEC.json").read_text())["acceptance_criteria"][
            0
        ]["expected"]["total"]
        == 99
    )


def test_synthetic_hardware_profile_draft_review_generate_and_fresh_tests(host):
    cli = str(ROOT / "tools/project_intake.py")
    specification = host / "hardware-request.json"
    drafted = run(
        host,
        cli,
        "draft",
        str(specification),
        "--slug",
        "synthetic-frame-parser",
        "--profile",
        intake.HARDWARE_PROFILE,
    )
    assert drafted.returncode == 0, drafted.stderr
    spec = json.loads(specification.read_text(encoding="utf-8"))
    assert spec["workflow"]["profile"] == intake.HARDWARE_PROFILE
    spec["purpose"] = (
        "Parse fictional device frames without communicating with hardware."
    )
    spec["open_questions"] = []
    specification.write_text(json.dumps(spec), encoding="utf-8")

    reviewed = run(host, cli, "review", str(specification))
    assert reviewed.returncode == 0, reviewed.stderr
    report = json.loads(reviewed.stdout)
    assert report["ready"]
    assert report["specification"] == spec
    assert "WORK_PACKET.json" in report["generated_files"]
    assert "contracts/synthetic_frame.py" in report["generated_files"]
    assert "src/features/synthetic_frame.py" in report["architecture"]
    target = host / "generated hardware project"
    generated = run(
        host,
        cli,
        "generate",
        str(specification),
        str(target),
        "--accept",
        report["fingerprint"],
        "--reviewed-by",
        "fixture-owner",
    )
    assert generated.returncode == 0, generated.stderr
    assert project_authority.status(target)["state"] == "AWAITING_APPROVAL"
    packet = json.loads((target / "WORK_PACKET.json").read_text(encoding="utf-8"))
    assert packet["domain"]["synthetic"] is True
    assert packet["domain"]["hardware_status"] == "UNVERIFIED_ON_HARDWARE"
    provenance = json.loads((target / "GENERATION.json").read_text(encoding="utf-8"))
    profile_files = [item for item in provenance["files"] if item["kind"] == "profile"]
    assert {item["destination"] for item in profile_files} == {
        "WORK_PACKET.json",
        "contracts/synthetic_frame.py",
        "src/features/synthetic_frame.py",
        "src/testing/synthetic_frame.py",
        "tests/test_parse_synthetic_frame_contract.py",
        "tests/test_hardware_profile.py",
    }
    assert all(item["source"] is not None for item in profile_files)
    assert len({item["destination"] for item in provenance["files"]}) == len(
        provenance["files"]
    )
    for item in provenance["files"]:
        assert (
            hashlib.sha256((target / item["destination"]).read_bytes()).hexdigest()
            == item["output_sha256"]
        )
        for extension in item.get("extensions", []):
            assert (
                hashlib.sha256((ROOT / extension["source"]).read_bytes()).hexdigest()
                == extension["source_sha256"]
            )
    result = run(
        target, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    parser = run(
        target,
        "-c",
        "from contracts import SyntheticFrameParser; "
        "from src.container.wiring import build_production_parser; "
        "parser = build_production_parser(); "
        "assert isinstance(parser, SyntheticFrameParser); "
        "assert parser.parse_synthetic_frame([161, 255]) == 255",
    )
    assert parser.returncode == 0, parser.stderr
    assert not (target / "config/project-approval.json").exists()

    # Use the packet's arguments, resolving its Python in this test environment.
    argv = packet["validation"][0]["command"]["argv"]
    assert argv[0] == "python"
    checked = run(target, *argv[1:])
    assert checked.returncode == 0, checked.stdout + checked.stderr
    count = re.search(r"Ran (\d+) tests?", checked.stderr)
    assert count and int(count[1]) > 0, checked.stderr

    # An isolated fixture proves the command actually checks parser behavior.
    parser_path = target / "src/features/synthetic_frame.py"
    original = parser_path.read_bytes()
    parser_path.write_text(
        "from contracts import SyntheticFrameParser\n"
        "class SyntheticByteFrameParser(SyntheticFrameParser):\n"
        "    def parse_synthetic_frame(self, frame):\n"
        "        return 0\n",
        encoding="utf-8",
    )
    try:
        rejected = run(target, *argv[1:])
        assert rejected.returncode != 0
        assert "FAIL" in rejected.stderr, rejected.stdout + rejected.stderr
    finally:
        parser_path.write_bytes(original)


def test_hardware_user_expected_outcomes_are_not_rewritten(host):
    spec = intake.draft("contradictory-frame", intake.HARDWARE_PROFILE)
    spec["open_questions"] = []
    spec["acceptance_criteria"] = [
        {"name": "wrong-payload", "frame": [161, 7], "expected": 8}
    ]
    target = host / "wrong-hardware-expectation"
    build(spec, target)
    result = run(
        target,
        "-m",
        "pytest",
        "tests/test_project_acceptance.py",
        "-q",
        "-o",
        "addopts=",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 failed" in result.stdout
    assert (
        json.loads((target / "PROJECT_SPEC.json").read_text())["acceptance_criteria"]
        == spec["acceptance_criteria"]
    )


@pytest.mark.parametrize("frame", [[True, 0], [161, -1], [161, 256], ["161", 0]])
def test_hardware_profile_rejects_non_byte_frames(host, frame):
    spec = intake.draft("hardware-check", intake.HARDWARE_PROFILE)
    spec["open_questions"] = []
    spec["acceptance_criteria"] = [{"name": "case", "frame": frame, "expected": 0}]
    with pytest.raises(ValueError):
        intake.validate(spec)


@pytest.mark.parametrize("expected", [True, -1, 256, "0"])
def test_hardware_profile_rejects_non_byte_expectations(host, expected):
    spec = intake.draft("hardware-check", intake.HARDWARE_PROFILE)
    spec["open_questions"] = []
    spec["acceptance_criteria"] = [
        {"name": "case", "frame": [161, 0], "expected": expected}
    ]
    with pytest.raises(ValueError):
        intake.validate(spec)


def test_cli_rejects_duplicate_json_keys_without_creating_project(host):
    path = host / "ambiguous.json"
    path.write_text('{"slug":"one","slug":"two"}')
    result = run(host, str(ROOT / "tools/project_intake.py"), "review", str(path))
    assert result.returncode == 1
    assert "Duplicate JSON key" in result.stderr
