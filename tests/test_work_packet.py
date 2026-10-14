from __future__ import annotations

import contextlib
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/work_packet.py"
SPEC = importlib.util.spec_from_file_location("work_packet_under_test", SCRIPT)
work_packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(work_packet)

PROFILES = ("software-hardware",)
PROFILE = PROFILES[0]
# The only canonical profile registers a domain module, so the generic path for a profile without
# one (work_packet.domain_errors returning no rules) is exercised by unregistering it for the test.
UNREGISTERED = "software-hardware"
STAMP = "2026-09-12T12:00:00Z"
EVIDENCE = ["synthetic-check-record-001"]
STEPS = (
    ("ARCHITECTED", "architect", "Synthetic architect"),
    ("READY", "architect", "Synthetic architect"),
    ("IN_PROGRESS", "worker", "Synthetic worker"),
    ("VALIDATING", "worker", "Synthetic worker"),
    ("REVIEW", "worker", "Synthetic worker"),
    ("ACCEPTED", "reviewer", "Independent reviewer"),
    ("MERGED", "integrator", "Synthetic integrator"),
    ("VERIFIED", "integrator", "Synthetic integrator"),
)


@contextlib.contextmanager
def unregistered(profile=UNREGISTERED):
    with mock.patch.dict(work_packet.DOMAIN_MODULES):
        del work_packet.DOMAIN_MODULES[profile]
        yield


def fixture(profile="software-hardware"):
    return work_packet.read_json(ROOT / "examples/work-packets" / f"{profile}.contract.json")


def packet(task_id="WP-SYN-001", profile="software-hardware", dependencies=()):
    contract = fixture(profile)
    contract["dependencies"] = list(dependencies)
    return work_packet.create(task_id, profile, contract, "Synthetic architect", "Synthetic fixture creation", STAMP)


def move(value, state, role, actor, evidence=EVIDENCE, graph=None):
    return work_packet.transition(value, state, role, actor, "Synthetic recorded transition", evidence, graph, STAMP)


def advance(value, target="VERIFIED"):
    if value["state"] == target:
        return value
    for state, role, actor in STEPS:
        value = move(value, state, role, actor)
        if state == target:
            return value
    raise AssertionError(f"Unsupported test target: {target}")


def reordered(value):
    if isinstance(value, dict):
        return {key: reordered(child) for key, child in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reordered(child) for child in value]
    return value


class ContractTests(unittest.TestCase):
    def test_optional_per_tier_caps_remain_inside_the_authorized_total_budget(self):
        contract = fixture()
        contract["retry_budget"]["max_attempts_by_tier"] = {"1": 2, "3": 1}
        self.assertEqual(work_packet.validate_contract(contract, PROFILE), [])
        original = copy.deepcopy(contract)
        for caps in ({}, {"0": 1}, {"1": 3}, {"1": 0}, {"5": 1}, {"1\n": 1}, {"1": True}):
            with self.subTest(caps=caps):
                candidate = copy.deepcopy(original)
                candidate["retry_budget"]["max_attempts_by_tier"] = caps
                self.assertTrue(work_packet.validate_contract(candidate, PROFILE))

    def test_all_profile_examples_create_independent_valid_snapshots(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                contract = fixture(profile)
                self.assertEqual(work_packet.validate_contract(contract, profile), [])
                value = work_packet.create("WP-SYN-001", profile, contract, "Architect", "Synthetic example", STAMP)
                self.assertEqual(work_packet.validate(value), [])
                self.assertEqual(value["state"], "PROPOSED")
                self.assertEqual(work_packet.current(value)["version"], 1)
                self.assertEqual(work_packet.current(value)["contract"], contract)
                contract["title"] = "Changed caller-owned input"
                self.assertNotEqual(work_packet.current(value)["contract"]["title"], contract["title"])

    def test_every_required_contract_field_is_enforced(self):
        required = (
            "title", "parent", "goal", "non_goals", "scope", "inputs", "outputs", "interface",
            "dependencies", "assumptions", "sources", "acceptance_criteria", "validation",
            "complexity", "risk", "routing", "retry_budget", "escalation_path", "context_scope",
            "architecture_boundaries", "domain",
        )
        for field in required:
            with self.subTest(field=field):
                contract = fixture()
                del contract[field]
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))

    def test_malformed_contract_fields_are_rejected_without_crashing(self):
        changes = (
            ("title", " \n\t"), ("non_goals", []), ("inputs", []), ("outputs", "text"),
            ("parent", {"objective": "Defined"}), ("scope", {"allowed": ["one"], "prohibited": []}),
            ("interface", {"name": "api", "version": " ", "description": "A description"}),
            ("sources", [{"id": "SRC-1", "reference": " ", "authority": "Synthetic only"}]),
            ("validation", [{"id": "VAL-1", "description": "Check", "criterion_ids": [], "evidence_required": []}]),
            ("complexity", "unbounded"), ("risk", "unknown"), ("domain", []),
            ("retry_budget", {"max_attempts": 0}), ("retry_budget", {"max_attempts": 21}),
            ("retry_budget", {"max_attempts": True}), ("dependencies", ["../unsafe"]),
            ("dependencies", ["SAME", "SAME"]), ("assumptions", [" "]),
            ("architecture_boundaries", []), ("context_scope", []),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                contract = fixture()
                contract[field] = value
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))
        for value in (None, [], "contract", 3):
            with self.subTest(root=value):
                self.assertTrue(work_packet.validate_contract(value, PROFILE))

    def test_only_domain_allows_extension_properties(self):
        for path in ((), ("parent",), ("scope",), ("interface",), ("routing",), ("retry_budget",), ("inputs", 0), ("sources", 0), ("acceptance_criteria", 0), ("validation", 0)):
            with self.subTest(path=path):
                contract = fixture()
                target = contract
                for key in path:
                    target = target[key]
                target["unexpected"] = "Not in the contract"
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))
        # The common schema leaves `domain` open for a profile without registered rules ...
        with unregistered():
            contract = fixture(UNREGISTERED)
            contract["domain"]["custom"] = {"nested": ["Synthetic extension", 7, None]}
            self.assertEqual(work_packet.validate_contract(contract, UNREGISTERED), [])
            contract["version"] = 2
            self.assertTrue(work_packet.validate_contract(contract, UNREGISTERED))
        # ... and a registered profile's module decides what its block admits (software-hardware closes it).
        contract = fixture()
        contract["domain"]["custom"] = "Not in the contract"
        self.assertTrue(any("Additional properties" in e for e in work_packet.validate_contract(contract, PROFILE)))

    def test_worker_instructions_are_optional_relative_paths(self):
        contract = fixture()
        self.assertNotIn("worker_instructions", contract, "existing contracts stay valid without it")
        for value in ([], ["AGENTS.md"], ["src/module/AGENTS.md", "docs/interface.md"]):
            with self.subTest(value=value):
                contract["worker_instructions"] = value
                self.assertEqual(work_packet.validate_contract(contract, PROFILE), [])
        for value in (["../outside.md"], ["/etc/passwd"], ["C:/x.md"], ["a/./b.md"], ["x|y.md"],
                      [""], ["same.md", "same.md"], [f"doc-{index}.md" for index in range(9)], "AGENTS.md"):
            with self.subTest(value=value):
                contract["worker_instructions"] = value
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))

    def test_validate_contract_requires_an_explicit_registered_profile(self):
        # A caller that does not say which profile it validates for would skip that profile's
        # domain rules silently; there is no default and None is refused.
        contract = fixture()
        with self.assertRaises(TypeError):
            work_packet.validate_contract(contract)  # the missing argument is the point
        for profile in (None, "", "generic", 3):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, "registered domain profile"):
                    work_packet.validate_contract(contract, profile)

    def test_criteria_require_known_references_and_complete_coverage(self):
        contract = fixture()
        contract["validation"][0]["criterion_ids"].append("UNKNOWN")
        self.assertIn("unknown criterion", "; ".join(work_packet.validate_contract(contract, PROFILE)))
        contract = fixture()
        contract["validation"][0]["criterion_ids"] = [contract["acceptance_criteria"][0]["id"]]
        self.assertIn("every criterion", "; ".join(work_packet.validate_contract(contract, PROFILE)))
        for field in ("acceptance_criteria", "validation", "sources"):
            with self.subTest(field=field):
                contract = fixture()
                contract[field].append(copy.deepcopy(contract[field][0]))
                self.assertIn("duplicate IDs", "; ".join(work_packet.validate_contract(contract, PROFILE)))

    def test_tier_ordering_bounds_and_attempt_budget(self):
        for minimum, maximum, escalation in ((3, 1, []), (1, 3, [3, 2]), (1, 3, [1, 2]), (1, 2, [3]), (1, 3, [2, 2])):
            with self.subTest(minimum=minimum, maximum=maximum, escalation=escalation):
                contract = fixture()
                contract["routing"].update(min_tier=minimum, max_tier=maximum)
                contract["escalation_path"] = escalation
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))
        for key, invalid in (("min_tier", -1), ("max_tier", 5), ("reviewer_tier", 5), ("min_tier", True), ("reasoning_effort", "automatic")):
            with self.subTest(key=key):
                contract = fixture()
                contract["routing"][key] = invalid
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))
        contract = fixture()
        contract["routing"].update(min_tier=0, max_tier=4, reviewer_tier=4)
        contract["escalation_path"] = [1, 2, 3, 4]
        contract["retry_budget"]["max_attempts"] = 20
        self.assertEqual(work_packet.validate_contract(contract, PROFILE), [])

    def test_packet_envelope_rejects_missing_and_malformed_fields(self):
        for field in ("schema_version", "task_id", "domain_profile", "state", "revision_history", "events"):
            with self.subTest(missing=field):
                value = packet()
                del value[field]
                self.assertTrue(work_packet.validate(value))
        for field, invalid in (("task_id", "../unsafe"), ("task_id", "x" * 81), ("schema_version", "2.0"), ("domain_profile", "other"), ("state", "DONE"), ("revision_history", []), ("events", []), ("contract", fixture())):
            with self.subTest(field=field):
                value = packet()
                value[field] = invalid
                self.assertTrue(work_packet.validate(value))
        for invalid in ("not-a-date", "2026-09-12T12:00:00", " "):
            with self.subTest(timestamp=invalid):
                value = packet()
                value["events"][0]["timestamp"] = invalid
                self.assertTrue(work_packet.validate(value))

    def test_schema_valid_integer_floats_and_lowercase_rfc3339_are_accepted(self):
        value = packet()
        value["events"][0]["revision"] = 1.0
        self.assertEqual(work_packet.validate(value), [])
        value = packet()
        lowercase = "2026-09-12t12:00:00z"
        value["revision_history"][0]["timestamp"] = lowercase
        value["events"][0]["timestamp"] = lowercase
        self.assertEqual(work_packet.validate(value), [])
        result = move(value, "ARCHITECTED", "architect", "Architect")
        self.assertEqual(result["state"], "ARCHITECTED")

    def test_identifiers_cannot_hide_a_trailing_newline(self):
        value = packet()
        value["task_id"] += "\n"
        self.assertTrue(work_packet.validate(value))
        for field in ("sources", "acceptance_criteria", "validation"):
            with self.subTest(field=field):
                contract = fixture()
                contract[field][0]["id"] += "\n"
                self.assertTrue(work_packet.validate_contract(contract, PROFILE))
        contract = fixture()
        contract["dependencies"] = ["UPSTREAM\n"]
        self.assertTrue(work_packet.validate_contract(contract, PROFILE))

    def test_invalid_dates_return_errors_for_both_event_and_revision_metadata(self):
        for invalid in ("not-a-date", "2026-02-30T12:00:00Z", "2026-09-12T25:00:00Z", "2026-09-12T12:00:00", "2026-09-12T12:00:00+25:00", "2026-09-12T12:00:00+00:99", "2026-09-12T12:00:00-01:60"):
            for section in ("events", "revision_history"):
                with self.subTest(timestamp=invalid, section=section):
                    value = packet()
                    value[section][0]["timestamp"] = invalid
                    self.assertTrue(work_packet.validate(value))

    def test_event_and_revision_provenance_requires_complete_nonblank_metadata(self):
        for section in ("events", "revision_history"):
            for field in ("actor", "timestamp", "reason"):
                with self.subTest(section=section, field=field):
                    value = packet()
                    del value[section][0][field]
                    self.assertTrue(work_packet.validate(value))
                    value = packet()
                    value[section][0][field] = " \t"
                    self.assertTrue(work_packet.validate(value))
            value = packet()
            value[section][0]["unrecognized"] = "Extra metadata"
            self.assertTrue(work_packet.validate(value))
        for field, invalid in (("sequence", 0), ("revision", 1.5), ("role", "owner"), ("kind", "execute"), ("evidence", [" "])):
            with self.subTest(field=field):
                value = packet()
                value["events"][0][field] = invalid
                self.assertTrue(work_packet.validate(value))


class LifecycleTests(unittest.TestCase):
    def test_all_profiles_complete_lifecycle_with_immutable_inputs(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                original = packet(profile=profile)
                preserved = copy.deepcopy(original)
                result = advance(original)
                self.assertEqual(original, preserved)
                self.assertEqual(result["state"], "VERIFIED")
                self.assertEqual(work_packet.validate(result), [])
                self.assertEqual(len(result["events"]), 9)
                self.assertEqual(result["revision_history"], original["revision_history"])

    def test_acceptance_can_be_verified_without_a_merge_assertion(self):
        value = advance(packet(), "ACCEPTED")
        result = move(value, "VERIFIED", "integrator", "Independent integrator")
        self.assertEqual(result["state"], "VERIFIED")
        self.assertNotIn("MERGED", [event["to"] for event in result["events"]])

    def test_illegal_state_jumps_and_roles_are_rejected(self):
        cases = (
            ("PROPOSED", "READY", "architect"), ("PROPOSED", "ARCHITECTED", "worker"),
            ("READY", "IN_PROGRESS", "architect"), ("IN_PROGRESS", "ACCEPTED", "reviewer"),
            ("REVIEW", "ACCEPTED", "worker"), ("ACCEPTED", "MERGED", "reviewer"),
            ("VERIFIED", "IN_PROGRESS", "worker"),
        )
        for initial, target, role in cases:
            with self.subTest(initial=initial, target=target, role=role):
                value = advance(packet(), initial)
                preserved = copy.deepcopy(value)
                with self.assertRaisesRegex(ValueError, "illegal transition/role"):
                    move(value, target, role, "Different actor")
                self.assertEqual(value, preserved)

    def test_worker_cannot_self_accept_by_changing_role_or_identity_case(self):
        value = advance(packet(), "REVIEW")
        for role, actor in (("worker", "Synthetic worker"), ("reviewer", "Synthetic worker"), ("reviewer", "  SYNTHETIC WORKER  ")):
            with self.subTest(role=role, actor=actor):
                with self.assertRaises(ValueError):
                    move(value, "ACCEPTED", role, actor)
        accepted = move(value, "ACCEPTED", "reviewer", "Separate person")
        self.assertEqual(accepted["state"], "ACCEPTED")

    def test_review_rework_preserves_all_implementation_actor_exclusions(self):
        value = advance(packet(), "REVIEW")
        value = move(value, "IN_PROGRESS", "reviewer", "Independent reviewer")
        value = move(value, "VALIDATING", "worker", "Second worker")
        value = move(value, "REVIEW", "worker", "Second worker")
        for actor in ("Synthetic worker", "Second worker"):
            with self.subTest(actor=actor):
                with self.assertRaisesRegex(ValueError, "cannot accept its own revision"):
                    move(value, "ACCEPTED", "reviewer", actor)

    def test_review_acceptance_integration_and_recovery_require_evidence(self):
        for initial, target, role in (("VALIDATING", "REVIEW", "worker"), ("REVIEW", "ACCEPTED", "reviewer"), ("REVIEW", "IN_PROGRESS", "reviewer"), ("ACCEPTED", "MERGED", "integrator"), ("MERGED", "VERIFIED", "integrator")):
            with self.subTest(target=target, initial=initial):
                with self.assertRaisesRegex(ValueError, "requires evidence"):
                    move(advance(packet(), initial), target, role, "Separate actor", [])
        for paused in ("BLOCKED", "ESCALATED", "NEEDS_DECISION", "ARCHITECTURE_CONFLICT", "FAILED"):
            with self.subTest(paused=paused):
                role = "architect" if paused == "NEEDS_DECISION" else "worker"
                value = move(advance(packet(), "IN_PROGRESS"), paused, role, "Synthetic actor")
                with self.assertRaisesRegex(ValueError, "requires evidence"):
                    move(value, "ARCHITECTED", "architect", "Architect", [])
                with self.assertRaisesRegex(ValueError, "illegal transition/role"):
                    move(value, "ARCHITECTED", "worker", "Worker")
                self.assertEqual(move(value, "ARCHITECTED", "architect", "Architect")["state"], "ARCHITECTED")

    def test_superseded_state_has_no_execution_transition(self):
        value = move(packet(), "SUPERSEDED", "architect", "Architect")
        with self.assertRaisesRegex(ValueError, "illegal transition/role"):
            move(value, "ARCHITECTED", "architect", "Architect")

    def test_forged_contract_hashes_and_identity_bindings_are_rejected(self):
        value = packet()
        value["task_id"] = "ANOTHER-TASK"
        self.assertIn("contract hash mismatch", "; ".join(work_packet.validate(value)))
        # With one canonical profile there is no other valid binding, so a foreign profile is refused outright.
        value = packet()
        value["domain_profile"] = "other-profile"
        self.assertTrue(work_packet.validate(value))
        value = packet()
        value["revision_history"][0]["contract"]["goal"] = "Unrecorded scope expansion"
        self.assertIn("contract hash mismatch", "; ".join(work_packet.validate(value)))
        value = packet()
        value["events"][0]["contract_hash"] = "0" * 64
        self.assertIn("contract hash does not match", "; ".join(work_packet.validate(value)))

    def test_forged_event_chains_and_revision_records_are_rejected(self):
        cases = (
            ("sequence", 2), ("from", "READY"), ("to", "ACCEPTED"), ("revision", 2),
            ("role", "worker"), ("actor", "Someone else"), ("reason", "Unmatched reason"),
            ("timestamp", "2026-09-12T12:01:00Z"), ("kind", "transition"),
        )
        for field, replacement in cases:
            with self.subTest(field=field):
                value = packet()
                value["events"][0][field] = replacement
                self.assertTrue(work_packet.validate(value))
        value = advance(packet(), "READY")
        del value["events"][1]
        self.assertTrue(work_packet.validate(value))
        value = packet()
        value["revision_history"][0]["version"] = 2
        self.assertTrue(work_packet.validate(value))
        value = packet()
        value["state"] = "VERIFIED"
        self.assertIn("does not match replayed events", "; ".join(work_packet.validate(value)))

    def test_backwards_transition_and_revision_timestamps_are_rejected(self):
        original = packet()
        with self.assertRaisesRegex(ValueError, "timestamps must not move backwards"):
            work_packet.transition(original, "ARCHITECTED", "architect", "Architect", "Reason", timestamp="2026-09-12T11:59:00Z")
        contract = fixture()
        contract["goal"] = "Changed goal"
        with self.assertRaisesRegex(ValueError, "timestamps must not move backwards"):
            work_packet.revise(original, contract, "Architect", "Changed scope", "2026-09-12T11:59:00Z")

    def test_revision_resets_state_preserves_history_and_rejects_stale_hash(self):
        original = advance(packet(), "ACCEPTED")
        preserved = copy.deepcopy(original)
        contract = copy.deepcopy(work_packet.current(original)["contract"])
        contract["goal"] = "A revised bounded synthetic goal"
        revised = work_packet.revise(original, contract, "Architect", "New scope requires new review", STAMP)
        self.assertEqual(original, preserved)
        self.assertEqual(revised["state"], "PROPOSED")
        self.assertEqual(revised["revision_history"][:-1], original["revision_history"])
        self.assertEqual(revised["events"][:-1], original["events"])
        self.assertEqual(work_packet.current(revised)["version"], 2)
        self.assertEqual(work_packet.current(revised)["contract"], contract)
        self.assertNotEqual(work_packet.current(revised)["hash"], work_packet.current(original)["hash"])
        self.assertEqual(work_packet.validate(revised), [])
        with self.assertRaises(ValueError):
            move(revised, "ACCEPTED", "reviewer", "Independent reviewer")
        stale = copy.deepcopy(revised)
        stale["events"][-1]["contract_hash"] = work_packet.current(original)["hash"]
        self.assertIn("contract hash does not match", "; ".join(work_packet.validate(stale)))
        with self.assertRaises(ValueError):
            move(stale, "ARCHITECTED", "architect", "Architect")
        revised["revision_history"][0]["contract"]["goal"] = "Rewritten past"
        self.assertIn("contract hash mismatch", "; ".join(work_packet.validate(revised)))

    def test_unchanged_revision_is_refused(self):
        value = packet()
        with self.assertRaisesRegex(ValueError, "does not change"):
            work_packet.revise(value, fixture(), "Architect", "No actual change", STAMP)


class DependencyGraphTests(unittest.TestCase):
    def test_graph_order_is_deterministic_and_places_dependencies_first(self):
        values = [packet("C"), packet("B", dependencies=["A"]), packet("A")]
        order = work_packet.graph_order(values)
        self.assertEqual(order, work_packet.graph_order(list(reversed(values))))
        self.assertEqual(set(order), {"A", "B", "C"})
        self.assertLess(order.index("A"), order.index("B"))

    def test_graph_rejects_empty_duplicate_missing_self_and_cycle(self):
        cases = (
            ([], "empty"), ([packet("A"), packet("A")], "duplicate task ID"),
            ([packet("B", dependencies=["MISSING"])], "missing dependencies"),
            ([packet("A", dependencies=["B"]), packet("B", dependencies=["A"])], "cycle"),
        )
        for values, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    work_packet.graph_order(values)
        with self.assertRaisesRegex(ValueError, "cannot depend on itself"):
            packet("SELF", dependencies=["SELF"])

    def test_advanced_transition_requires_complete_verified_dependency_graph(self):
        dependent = move(packet("B", dependencies=["A"]), "ARCHITECTED", "architect", "Architect")
        with self.assertRaisesRegex(ValueError, "complete --graph"):
            move(dependent, "READY", "architect", "Architect")
        with self.assertRaisesRegex(ValueError, "missing dependencies"):
            move(dependent, "READY", "architect", "Architect", graph=[dependent])
        with self.assertRaisesRegex(ValueError, "must be VERIFIED"):
            move(dependent, "READY", "architect", "Architect", graph=[packet("A"), dependent])
        verified = advance(packet("A"))
        ready = move(dependent, "READY", "architect", "Architect", graph=[verified, dependent])
        self.assertEqual(ready["state"], "READY")
        self.assertEqual(work_packet.graph_order([ready, verified]), ["A", "B"])

    def test_graph_rejects_stale_or_duplicate_target_packet(self):
        previous = packet("B", dependencies=["A"])
        current = move(previous, "ARCHITECTED", "architect", "Architect")
        dependency = advance(packet("A"))
        for graph in ([dependency, previous], [dependency], [dependency, current, current]):
            with self.subTest(target_count=len(graph)):
                with self.assertRaisesRegex(ValueError, "exactly the current target packet"):
                    move(current, "READY", "architect", "Architect", graph=graph)

    def test_transition_rejects_malformed_graph_members_without_crashing(self):
        value = advance(packet(), "ARCHITECTED")
        for malformed in (None, [], 7, "not a packet"):
            with self.subTest(member=malformed):
                with self.assertRaises(ValueError):
                    move(value, "READY", "architect", "Architect", graph=[value, malformed])

    def test_revised_or_tampered_dependency_invalidates_advanced_graph(self):
        dependency = advance(packet("A"))
        dependent = move(packet("B", dependencies=["A"]), "ARCHITECTED", "architect", "Architect")
        dependent = move(dependent, "READY", "architect", "Architect", graph=[dependency, dependent])
        contract = fixture()
        contract["goal"] = "Revised dependency scope"
        revised = work_packet.revise(dependency, contract, "Architect", "Dependency changed", STAMP)
        with self.assertRaisesRegex(ValueError, "must be VERIFIED"):
            work_packet.graph_order([revised, dependent])
        tampered = copy.deepcopy(dependency)
        tampered["revision_history"][0]["contract"]["goal"] = "Unrecorded change"
        with self.assertRaisesRegex(ValueError, "contract hash mismatch"):
            work_packet.graph_order([tampered, dependent])


class RendererTests(unittest.TestCase):
    @unregistered()  # arbitrary extension JSON, which only a profile without a module admits
    def test_renderer_is_identical_after_all_json_object_keys_are_reordered(self):
        value = packet(profile=UNREGISTERED)
        contract = fixture(UNREGISTERED)
        contract["domain"]["nested"] = {"zebra": {"beta": "Second", "alpha": "First"}, "alpha": [1, 2]}
        value = work_packet.revise(value, contract, "Architect", "Synthetic nested extension", STAMP)
        equivalent = json.loads(json.dumps(reordered(value)))
        self.assertEqual(work_packet.validate(equivalent), [])
        self.assertEqual(work_packet.render(value), work_packet.render(equivalent))

    def test_renderer_contains_every_contract_section_and_provenance(self):
        sections = (
            "Parent", "Goal", "Non goals", "Scope", "Inputs", "Outputs", "Interface", "Dependencies",
            "Assumptions", "Sources", "Acceptance criteria", "Validation", "Complexity", "Risk", "Routing",
            "Retry budget", "Escalation path", "Context scope", "Architecture boundaries", "Domain",
        )
        for profile in PROFILES:
            with self.subTest(profile=profile):
                value = packet(profile=profile)
                rendered = work_packet.render(value)
                for section in sections:
                    self.assertIn(f"## {section}\n", rendered)
                self.assertIn(work_packet.current(value)["hash"], rendered)
                self.assertIn("Revision: 1", rendered)
                self.assertIn("## Revision provenance", rendered)
                self.assertIn("## Latest recorded event", rendered)
                self.assertIn("do not authorize execution", rendered)
                self.assertIn("independently prove", rendered)

    @unregistered()  # arbitrary extension JSON, which only a profile without a module admits
    def test_domain_render_preserves_json_types_keys_and_nested_arrays(self):
        contract = fixture(UNREGISTERED)
        contract["domain"] = {"Exact_Key": [None, "None", True, "True", 1, "1", [], {},
            [False, "false", {"CaseSensitive": "```\n## embedded fence"}]], "exact_key": None}
        value = work_packet.create("WP-TYPES", UNREGISTERED, contract, "Architect", "Typed data", STAMP)
        rendered = work_packet.render(value)
        block = rendered.split("## Domain\n\n", 1)[1].split("\n\n## Revision provenance", 1)[0]
        lines = block.splitlines()
        self.assertEqual(lines[0], "````json")
        self.assertEqual(lines[-1], "````")
        decoded = json.loads("\n".join(lines[1:-1]))
        self.assertEqual(decoded, contract["domain"])
        self.assertEqual([type(item) for item in decoded["Exact_Key"][:6]],
                         [type(None), str, bool, str, int, str])

    @unregistered()  # arbitrary extension JSON, which only a profile without a module admits
    def test_renderer_uses_latest_revision_and_escapes_embedded_markup(self):
        value = packet(profile=UNREGISTERED)
        contract = fixture(UNREGISTERED)
        contract["title"] = "Latest synthetic title"
        contract["goal"] = "<script>alert(1)</script>\n# Injected heading"
        contract["domain"]["nested"] = {"message": "DEEPVALUE"}
        revised = work_packet.revise(value, contract, "Architect", "Update proposal", STAMP)
        rendered = work_packet.render(revised)
        self.assertIn("Latest synthetic title", rendered)
        self.assertIn("Revision: 2", rendered)
        self.assertIn("DEEPVALUE", rendered)
        self.assertIn(work_packet.current(value)["hash"], rendered)
        self.assertIn(work_packet.current(revised)["hash"], rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("\n# Injected heading", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.contract_path = self.write_json("contract.json", fixture())

    def write_json(self, name, data):
        path = self.directory / name
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)], cwd=self.directory,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def create_arguments(self, output, source=None):
        return ("create", source or self.contract_path, "--task-id", "WP-CLI-001", "--profile", "software-hardware", "--actor", "Synthetic architect", "--reason", "Synthetic CLI fixture", "--output", output)

    def assert_failed(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WORK PACKET INVALID", result.stderr)

    def test_cli_create_validate_render_and_revise_preserve_source_files(self):
        source_bytes = self.contract_path.read_bytes()
        output = self.directory / "packet.json"
        result = self.cli(*self.create_arguments(output))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no work executed", result.stdout)
        self.assertEqual(self.contract_path.read_bytes(), source_bytes)
        original_bytes = output.read_bytes()
        value = work_packet.read_json(output)
        self.assertEqual(work_packet.validate(value), [])
        result = self.cli("validate", output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no execution authorization", result.stdout)
        rendered = self.directory / "issue.md"
        result = self.cli("render", output, "--output", rendered)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(rendered.read_text(encoding="utf-8"), work_packet.render(value))
        stdout_render = self.cli("render", output)
        self.assertEqual(stdout_render.returncode, 0, stdout_render.stderr)
        self.assertEqual(stdout_render.stdout, rendered.read_text(encoding="utf-8"))
        changed = fixture()
        changed["goal"] = "Revised synthetic CLI goal"
        revised_contract = self.write_json("changed-contract.json", changed)
        changed_bytes = revised_contract.read_bytes()
        revised_path = self.directory / "revision-2.json"
        result = self.cli("revise", output, "--contract", revised_contract, "--actor", "Architect", "--reason", "Scope revision", "--output", revised_path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        revised = work_packet.read_json(revised_path)
        self.assertEqual(work_packet.current(revised)["version"], 2)
        self.assertEqual(revised["revision_history"][:-1], value["revision_history"])
        self.assertEqual(revised["state"], "PROPOSED")
        self.assertEqual(output.read_bytes(), original_bytes)
        self.assertEqual(revised_contract.read_bytes(), changed_bytes)

    def test_cli_existing_outputs_and_input_aliases_are_never_overwritten(self):
        packet_path = self.write_json("packet.json", packet())
        revised_contract = fixture()
        revised_contract["goal"] = "Changed goal"
        revised_path = self.write_json("revised-contract.json", revised_contract)
        existing = self.directory / "existing.txt"
        existing.write_bytes(b"Preserve this exact content\r\n")
        commands = (
            self.create_arguments(existing), self.create_arguments(self.contract_path),
            ("render", packet_path, "--output", existing), ("render", packet_path, "--output", packet_path),
            ("revise", packet_path, "--contract", revised_path, "--actor", "Architect", "--reason", "Changed scope", "--output", existing),
            ("revise", packet_path, "--contract", revised_path, "--actor", "Architect", "--reason", "Changed scope", "--output", packet_path),
        )
        protected = {path: path.read_bytes() for path in (self.contract_path, packet_path, revised_path, existing)}
        for arguments in commands:
            with self.subTest(command=arguments[0], output=str(arguments[-1])):
                self.assert_failed(self.cli(*arguments))
                for path, expected in protected.items():
                    self.assertEqual(path.read_bytes(), expected)

    def test_cli_refuses_malformed_create_without_writing_output(self):
        for invalid in ({}, {**fixture(), "title": " "}, {**fixture(), "dependencies": ["../bad"]}):
            with self.subTest(invalid=invalid.get("title", "missing")):
                source = self.write_json("invalid-contract.json", invalid)
                before = source.read_bytes()
                output = self.directory / "refused.json"
                self.assert_failed(self.cli(*self.create_arguments(output, source)))
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)

    def test_cli_invalid_render_and_unchanged_revision_leave_no_output(self):
        source = self.write_json("packet.json", packet())
        before = source.read_bytes()
        output = self.directory / "refused.json"
        result = self.cli("revise", source, "--contract", self.contract_path, "--actor", "Architect", "--reason", "No change", "--output", output)
        self.assert_failed(result)
        self.assertIn("does not change", result.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(source.read_bytes(), before)
        invalid = packet()
        invalid["revision_history"][0]["contract"]["goal"] = "Unrecorded change"
        invalid_path = self.write_json("tampered.json", invalid)
        result = self.cli("render", invalid_path, "--output", output)
        self.assert_failed(result)
        self.assertIn("contract hash mismatch", result.stderr)
        self.assertFalse(output.exists())

    def test_read_json_and_cli_reject_malformed_duplicate_and_nonfinite_json(self):
        samples = ('{"title":', '{"title":"one","title":"two"}', '{"domain":{"same":1,"same":2}}', '{"domain":NaN}', '{"domain":Infinity}', '{"domain":-Infinity}')
        for sample in samples:
            with self.subTest(sample=sample):
                source = self.directory / "bad.json"
                source.write_text(sample, encoding="utf-8")
                before = source.read_bytes()
                with self.assertRaises(ValueError):
                    work_packet.read_json(source)
                output = self.directory / "refused.json"
                self.assert_failed(self.cli(*self.create_arguments(output, source)))
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)

    def test_cli_malformed_graph_fails_cleanly_and_preserves_input(self):
        source = self.write_json("architected.json", advance(packet(), "ARCHITECTED"))
        before = source.read_bytes()
        for malformed in (None, [], 7, "not a packet"):
            with self.subTest(member=malformed):
                graph_member = self.write_json("malformed-graph-member.json", malformed)
                output = self.directory / "refused.json"
                result = self.cli(
                    "transition", source, "--to", "READY", "--role", "architect",
                    "--actor", "Architect", "--reason", "Synthetic graph check", "--output", output,
                    "--graph", source, graph_member,
                )
                self.assert_failed(result)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
