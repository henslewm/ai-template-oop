from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/model_router.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("model_router_under_test", SCRIPT)
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)
wp = router.wp
STAMP = "2026-09-12T12:00:00Z"


def make_packet(
    state="READY",
    minimum=1,
    maximum=4,
    path=None,
    reviewer=4,
    effort="medium",
    risk="low",
    complexity="low",
    retries=8,
):
    contract = wp.read_json(
        ROOT / "examples/work-packets/software-hardware.contract.json"
    )
    contract["routing"] = {
        "min_tier": minimum,
        "max_tier": maximum,
        "reviewer_tier": reviewer,
        "reasoning_effort": effort,
    }
    contract["escalation_path"] = (
        list(range(minimum + 1, maximum + 1)) if path is None else path
    )
    contract["risk"], contract["complexity"] = risk, complexity
    contract["retry_budget"]["max_attempts"] = retries
    value = wp.create(
        "ROUTER-SYN-001",
        "software-hardware",
        contract,
        "Architect",
        "Synthetic router fixture",
        STAMP,
    )
    if state == "PROPOSED":
        return value
    for target, role, actor in (
        ("ARCHITECTED", "architect", "Architect"),
        ("READY", "architect", "Architect"),
        ("IN_PROGRESS", "worker", "Worker"),
        ("VALIDATING", "worker", "Worker"),
        ("REVIEW", "worker", "Worker"),
        ("ACCEPTED", "reviewer", "Independent reviewer"),
    ):
        value = wp.transition(
            value,
            target,
            role,
            actor,
            "Synthetic state assertion",
            ["synthetic-state-evidence"],
            timestamp=STAMP,
        )
        if target == state:
            return value
    raise AssertionError(f"Unsupported fixture state: {state}")


def resource(
    identifier="local",
    tier=1,
    provider="lmstudio",
    api=0,
    latency=1,
    acceptance=1,
    effort="medium",
    churn=0,
    review=0,
    regression=0,
):
    # For the default 1000 input + 1000 output tokens, the rate yields api dollars.
    return {
        "id": identifier,
        "provider_id": provider,
        "model": f"fictional-{identifier}",
        "enabled": True,
        "tier": tier,
        "context_window": 100000,
        "input_million_usd": api * 500,
        "output_million_usd": api * 500,
        "efforts": {
            effort: {
                "acceptance_probability": acceptance,
                "latency_seconds": latency,
                "context_churn_tokens": churn,
                "review_minutes": review,
                "regression_probability": regression,
            }
        },
    }


def config(*resources):
    value = wp.read_json(ROOT / "config/model-router.json")
    value["resources"] = list(resources) if resources else [resource()]
    value["policy"].update(
        role_api_budget_usd=10000,
        wall_second_usd=1,
        review_minute_usd=1,
        regression_usd=10,
    )
    return value


def request(packet, role="worker", attempts=()):
    latest = wp.current(packet)
    return {
        "schema_version": "1.0",
        "binding": {
            "task_id": packet["task_id"],
            "revision": latest["version"],
            "contract_hash": latest["hash"],
            "role": role,
        },
        "task_class": "synthetic-parser",
        "input_tokens": 1000,
        "output_tokens": 1000,
        "unavailable_providers": [],
        "unavailable_resources": [],
        "attempts": list(attempts),
        "observations": [],
    }


def attempt(
    sequence=1, tier=1, outcome="FAIL", provider="lmstudio", resource_id="local", api=0
):
    return {
        "sequence": sequence,
        "resource_id": resource_id,
        "provider_id": provider,
        "tier": tier,
        "outcome": outcome,
        "api_cost_usd": api,
        "elapsed_seconds": 2,
        "decision_id": f"{sequence:064x}",
        "config_hash": "b" * 64,
        "evidence": ["synthetic-attempt-evidence"],
    }


def observation(resource_id="local", task_class="synthetic-parser", effort="medium"):
    return {
        "resource_id": resource_id,
        "task_class": task_class,
        "reasoning_effort": effort,
        "samples": 5,
        "accepted": 2,
        "mean_latency_seconds": 2,
        "mean_context_churn_tokens": 0,
        "mean_review_minutes": 0,
        "regressions": 1,
        "source": "Synthetic aggregate; no real model-performance claim",
    }


class RoutingTests(unittest.TestCase):
    def assert_selected(self, decision, identifier):
        self.assertEqual(decision["status"], "ROUTED", decision)
        self.assertEqual(decision["selected"]["resource_id"], identifier)
        self.assertIs(decision["execution_authorized"], False)

    def assert_stop(self, decision, reason):
        self.assertEqual(decision["status"], "STOP", decision)
        self.assertEqual(decision["reason_codes"], [reason])
        self.assertIsNone(decision["selected"])
        self.assertIs(decision["execution_authorized"], False)

    def test_local_resource_wins_when_total_accepted_result_cost_is_lower(self):
        packet = make_packet()
        settings = config(
            resource(), resource("paid", tier=2, provider="mistral", api=1)
        )
        result = router.route(packet, settings, request(packet))
        self.assert_selected(result, "local")
        scores = {
            item["resource_id"]: item["expected_cost_per_accepted_result_usd"]
            for item in result["candidates"]
        }
        self.assertEqual(scores, {"local": 1, "paid": 2})

    def test_zero_api_cost_loses_when_time_or_acceptance_cost_is_worse(self):
        packet = make_packet()
        for local in (resource(latency=100), resource(acceptance=0.6)):
            with self.subTest(estimates=local["efforts"]):
                settings = config(
                    local, resource("paid", tier=2, provider="mistral", api=0.1)
                )
                self.assert_selected(
                    router.route(packet, settings, request(packet)), "paid"
                )

    def test_unreliable_zero_cost_resource_is_ineligible(self):
        packet = make_packet()
        settings = config(
            resource(acceptance=0.4, latency=0),
            resource("reliable", tier=2, provider="mistral", api=1),
        )
        result = router.route(packet, settings, request(packet))
        self.assert_selected(result, "reliable")
        local = next(
            item for item in result["candidates"] if item["resource_id"] == "local"
        )
        self.assertIn("BELOW_RELIABILITY_FLOOR", local["reason_codes"])

    def test_risk_and_complexity_floors_override_cheaper_lower_tiers(self):
        settings = config(
            *(
                resource(f"tier-{tier}", tier=tier, latency=tier + 1)
                for tier in range(5)
            )
        )
        for risk, complexity, expected in (
            ("high", "low", 3),
            ("critical", "low", 4),
            ("low", "medium", 2),
            ("low", "high", 3),
            ("medium", "low", 1),
        ):
            with self.subTest(risk=risk, complexity=complexity):
                packet = make_packet(minimum=0, risk=risk, complexity=complexity)
                result = router.route(packet, settings, request(packet))
                self.assert_selected(result, f"tier-{expected}")
                self.assertEqual(result["effective_floor"], expected)

    def test_effort_must_match_exactly_and_is_returned_with_selection(self):
        packet = make_packet(effort="high")
        settings = config(
            resource(effort="medium", latency=0),
            resource("exact", tier=2, effort="high"),
        )
        result = router.route(packet, settings, request(packet))
        self.assert_selected(result, "exact")
        self.assertEqual(result["selected"]["reasoning_effort"], "high")
        row = next(
            item for item in result["candidates"] if item["resource_id"] == "local"
        )
        self.assertIn("UNSUPPORTED_EFFORT", row["reason_codes"])

    def test_only_declared_worker_tier_path_is_authorized(self):
        packet = make_packet(path=[3])
        settings = config(
            resource("unauthorized", tier=2, latency=0),
            resource("authorized", tier=3, latency=10),
        )
        result = router.route(packet, settings, request(packet))
        self.assert_selected(result, "authorized")
        self.assertEqual(result["allowed_tiers"], [1, 3])

    def test_reviewer_exact_tier_may_be_outside_worker_maximum(self):
        packet = make_packet(state="REVIEW", maximum=1, path=[], reviewer=4)
        settings = config(
            resource("worker", tier=1, latency=0),
            resource("reviewer", tier=4, latency=2),
        )
        result = router.route(packet, settings, request(packet, "reviewer"))
        self.assert_selected(result, "reviewer")
        self.assertEqual(result["allowed_tiers"], [4])
        self.assertEqual(result["binding"]["role"], "reviewer")

    def test_reviewer_cannot_increase_its_tier_to_satisfy_a_higher_floor(self):
        packet = make_packet(state="REVIEW", reviewer=3, risk="critical")
        settings = config(resource("tier-3", tier=3), resource("tier-4", tier=4))
        self.assert_stop(
            router.route(packet, settings, request(packet, "reviewer")),
            "AUTHORIZED_TIER_PATH_EXHAUSTED",
        )

    def test_worker_and_reviewer_use_separate_attempt_limits(self):
        settings = config(resource("tier-4", tier=4), resource())
        settings["policy"]["max_review_attempts"] = 2
        reviewing = make_packet(state="REVIEW", retries=1)
        review_request = request(
            reviewing, "reviewer", [attempt(tier=4, resource_id="tier-4")]
        )
        result = router.route(reviewing, settings, review_request)
        self.assert_selected(result, "tier-4")
        self.assertEqual(result["remaining_attempts"], 1)
        review_request["attempts"].append(attempt(2, tier=4, resource_id="tier-4"))
        self.assert_stop(
            router.route(reviewing, settings, review_request),
            "ATTEMPT_BUDGET_EXHAUSTED",
        )
        working = make_packet(retries=1)
        self.assert_stop(
            router.route(working, settings, request(working, attempts=[attempt()])),
            "ATTEMPT_BUDGET_EXHAUSTED",
        )

    def test_provider_outage_prefers_eligible_same_tier_before_cheaper_higher_tier(
        self,
    ):
        packet = make_packet()
        settings = config(
            resource(),
            resource("same-tier", provider="mistral", latency=100),
            resource("higher-cheap", tier=2, provider="openai", latency=0),
        )
        result = router.route(
            packet,
            settings,
            request(packet, attempts=[attempt(outcome="PROVIDER_UNAVAILABLE")]),
        )
        self.assert_selected(result, "same-tier")
        self.assertEqual(result["reason_codes"], ["EQUIVALENT_TIER_FALLBACK"])

    def test_outage_can_escalate_after_same_tier_alternatives_are_ineligible(self):
        packet = make_packet()
        settings = config(
            resource(),
            resource("same-tier", provider="mistral", acceptance=0.1),
            resource("higher", tier=2, provider="openai"),
        )
        result = router.route(
            packet,
            settings,
            request(packet, attempts=[attempt(outcome="PROVIDER_UNAVAILABLE")]),
        )
        self.assert_selected(result, "higher")
        self.assertEqual(result["reason_codes"], ["ESCALATED_WITHIN_CONTRACT"])

    def test_availability_search_does_not_create_attempts_or_spend(self):
        packet = make_packet()
        settings = config(resource(), resource("available", tier=2, provider="mistral"))
        inputs = request(packet)
        inputs["unavailable_providers"] = ["lmstudio"]
        result = router.route(packet, settings, inputs)
        self.assert_selected(result, "available")
        self.assertEqual(result["attempt_number"], 1)
        self.assertEqual(result["remaining_attempts"], 2)
        self.assertEqual(result["recorded_api_spend_usd"], 0)
        self.assertEqual(inputs["attempts"], [])
        inputs["unavailable_resources"] = ["available"]
        self.assert_stop(router.route(packet, settings, inputs), "NO_ELIGIBLE_RESOURCE")

    def test_zero_api_budget_still_allows_zero_api_cost_resource(self):
        packet = make_packet()
        settings = config(resource(), resource("paid", tier=2, api=0.01, latency=0))
        settings["policy"]["role_api_budget_usd"] = 0
        self.assert_selected(router.route(packet, settings, request(packet)), "local")

    def test_terminal_outcomes_stop_routing_without_asserting_acceptance(self):
        packet = make_packet()
        for outcome, reason in (
            ("PASS", "PASS_REQUIRES_ACCEPTANCE_GATES"),
            ("BLOCKED", "TASK_BLOCKED"),
            ("ARCHITECTURE_CONFLICT", "ARCHITECTURE_CHANGE_GATE"),
        ):
            with self.subTest(outcome=outcome):
                result = router.route(
                    packet,
                    config(),
                    request(packet, attempts=[attempt(outcome=outcome)]),
                )
                self.assert_stop(result, reason)

    def test_state_gate_is_specific_to_worker_and_reviewer_role(self):
        for state, role in (
            ("PROPOSED", "worker"),
            ("REVIEW", "worker"),
            ("READY", "reviewer"),
            ("ACCEPTED", "reviewer"),
        ):
            with self.subTest(state=state, role=role):
                packet = make_packet(state=state)
                self.assert_stop(
                    router.route(packet, config(), request(packet, role)),
                    "PACKET_NOT_READY_FOR_ROLE",
                )
        for state in ("READY", "IN_PROGRESS"):
            with self.subTest(allowed_state=state):
                packet = make_packet(state=state)
                self.assert_selected(
                    router.route(packet, config(), request(packet)), "local"
                )

    def test_context_capacity_includes_input_output_and_estimated_churn(self):
        packet = make_packet()
        small = resource("too-small", churn=1, latency=0)
        small["context_window"] = 2000
        settings = config(small, resource("fits", tier=2))
        result = router.route(packet, settings, request(packet))
        self.assert_selected(result, "fits")
        row = next(
            item for item in result["candidates"] if item["resource_id"] == "too-small"
        )
        self.assertIn("CONTEXT_CAPACITY_EXCEEDED", row["reason_codes"])


class ValidationAndHistoryTests(unittest.TestCase):
    def test_native_validator_refuses_weakened_limits_without_changing_source_replay(
        self,
    ):
        for field, value in (("max_review_attempts", 8), ("failures_per_tier", 3)):
            settings = config()
            settings["policy"][field] = value
            router.source_validate_config(settings)
            with self.assertRaises(ValueError):
                router.validate_config(settings)
        settings = config()
        settings["policy"]["risk_floor"]["high"] = 2
        router.source_validate_config(settings)
        with self.assertRaisesRegex(ValueError, "floor"):
            router.validate_config(settings)

    def test_configuration_rejects_duplicate_unknown_nonmonotonic_and_malformed_values(
        self,
    ):
        invalids = []
        value = config()
        value["providers"].append({**value["providers"][0], "adapter": "different"})
        invalids.append(value)
        value = config()
        value["resources"].append({**value["resources"][0], "model": "different"})
        invalids.append(value)
        value = config()
        value["resources"][0]["provider_id"] = "missing"
        invalids.append(value)
        value = config()
        value["policy"]["risk_floor"]["low"] = 4
        invalids.append(value)
        value = config()
        value["policy"]["complexity_floor"]["low"] = 4
        invalids.append(value)
        value = config()
        value["policy"]["min_acceptance"]["low"] = 1
        invalids.append(value)
        value = config()
        value["resources"][0]["efforts"] = {}
        invalids.append(value)
        value = config()
        value["resources"][0]["id"] += "\n"
        invalids.append(value)
        value = config()
        value["policy"]["role_api_budget_usd"] = -1
        invalids.append(value)
        value = config()
        value["policy"]["max_review_attempts"] = 21
        invalids.append(value)
        value = config()
        value["resources"][0]["efforts"]["medium"]["acceptance_probability"] = 0
        invalids.append(value)
        packet = make_packet()
        for index, settings in enumerate(invalids):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    router.route(packet, settings, request(packet))

    def test_missing_fields_and_nonfinite_values_are_rejected_via_python_api(self):
        packet = make_packet()
        for field in (
            "schema_version",
            "binding",
            "task_class",
            "input_tokens",
            "output_tokens",
            "unavailable_providers",
            "unavailable_resources",
            "attempts",
            "observations",
        ):
            with self.subTest(missing=field):
                inputs = request(packet)
                del inputs[field]
                with self.assertRaises(ValueError):
                    router.route(packet, config(), inputs)
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(nonfinite=value):
                settings = config()
                settings["policy"]["wall_second_usd"] = value
                with self.assertRaises(ValueError):
                    router.route(packet, settings, request(packet))
                inputs = request(packet)
                inputs["input_tokens"] = value
                with self.assertRaises(ValueError):
                    router.route(packet, config(), inputs)

    def test_history_binding_matches_exact_task_and_revision(self):
        packet = make_packet()
        for field, value in (
            ("task_id", "OTHER"),
            ("revision", 2),
            ("contract_hash", "0" * 64),
        ):
            with self.subTest(field=field):
                inputs = request(packet)
                inputs["binding"][field] = value
                with self.assertRaisesRegex(
                    ValueError, "different task or contract revision"
                ):
                    router.route(packet, config(), inputs)
        contract = copy.deepcopy(wp.current(packet)["contract"])
        contract["goal"] = "Revised bounded goal"
        revised = wp.revise(packet, contract, "Architect", "New contract", STAMP)
        with self.assertRaisesRegex(ValueError, "different task or contract revision"):
            router.route(revised, config(), request(packet))

    def test_history_rejects_gaps_downward_tiers_terminal_continuation_and_ignored_escalation(
        self,
    ):
        packet = make_packet()
        histories = (
            [attempt(2)],
            [attempt(1, tier=2), attempt(2, tier=1)],
            [attempt(1, outcome="PASS"), attempt(2)],
            [attempt(1, outcome="BLOCKED"), attempt(2)],
            [attempt(1, outcome="NEEDS_ESCALATION"), attempt(2)],
            [attempt(1, outcome="PROVIDER_UNAVAILABLE"), attempt(2, tier=2)],
        )
        for history in histories:
            with self.subTest(
                history=[
                    (item["sequence"], item["tier"], item["outcome"])
                    for item in history
                ]
            ):
                with self.assertRaises(ValueError):
                    router.route(packet, config(), request(packet, attempts=history))
        duplicate = [attempt(1), attempt(2)]
        duplicate[1]["decision_id"] = duplicate[0]["decision_id"]
        with self.assertRaises(ValueError):
            router.route(packet, config(), request(packet, attempts=duplicate))

    def test_history_cannot_exceed_role_limit_or_escape_authorized_tiers(self):
        packet = make_packet(retries=1, path=[])
        with self.assertRaisesRegex(ValueError, "total role attempt budget"):
            router.route(
                packet, config(), request(packet, attempts=[attempt(1), attempt(2)])
            )
        with self.assertRaisesRegex(ValueError, "violates the contract"):
            router.route(packet, config(), request(packet, attempts=[attempt(tier=2)]))
        reviewer = make_packet(state="REVIEW", reviewer=4)
        with self.assertRaisesRegex(ValueError, "violates the contract"):
            router.route(
                reviewer, config(), request(reviewer, "reviewer", [attempt(tier=1)])
            )

    def test_role_binding_keeps_cost_and_retry_histories_separate(self):
        settings = config(resource(), resource("reviewer", tier=4))
        settings["policy"]["role_api_budget_usd"] = 1
        working = make_packet()
        worker_request = request(working, attempts=[attempt(api=1)])
        worker = router.route(working, settings, worker_request)
        reviewing = make_packet(state="REVIEW")
        reviewer_request = request(reviewing, "reviewer")
        reviewer = router.route(reviewing, settings, reviewer_request)
        self.assertEqual(worker["reason_codes"], ["API_BUDGET_EXHAUSTED"])
        self.assertEqual(reviewer["status"], "ROUTED")
        self.assertEqual(reviewer["attempt_number"], 1)
        self.assertEqual(reviewer["recorded_api_spend_usd"], 0)
        self.assertNotEqual(worker["binding"]["role"], reviewer["binding"]["role"])
        self.assertNotEqual(worker["request_hash"], reviewer["request_hash"])

    def test_config_swap_retains_history_cost_and_escalation_position(self):
        packet = make_packet()
        old_config = config(resource("retired", tier=2, provider="mistral"))
        old_decision = router.route(packet, old_config, request(packet))
        history = attempt(tier=2, provider="mistral", resource_id="retired", api=0.25)
        history.update(
            decision_id=old_decision["decision_id"],
            config_hash=old_decision["config_hash"],
        )
        new_config = config(
            resource(latency=0),
            resource("replacement", tier=2, provider="openai", latency=10),
        )
        result = router.route(packet, new_config, request(packet, attempts=[history]))
        self.assertEqual(result["selected"]["resource_id"], "replacement")
        self.assertEqual(result["effective_floor"], 2)
        self.assertEqual(result["recorded_api_spend_usd"], 0.25)
        self.assertNotEqual(result["config_hash"], old_decision["config_hash"])

    def test_observation_counts_and_aggregate_identity_are_validated(self):
        packet = make_packet()
        for field in ("accepted", "regressions"):
            with self.subTest(field=field):
                item = observation()
                item[field] = item["samples"] + 1
                inputs = request(packet)
                inputs["observations"] = [item]
                with self.assertRaisesRegex(ValueError, "counts exceed samples"):
                    router.route(packet, config(), inputs)
        inputs = request(packet)
        inputs["observations"] = [observation(), observation()]
        with self.assertRaisesRegex(ValueError, "Duplicate observation aggregate"):
            router.route(packet, config(), inputs)


class TelemetryAndReplayTests(unittest.TestCase):
    def test_schema_bound_extreme_estimates_produce_finite_trace_without_exception(
        self,
    ):
        packet = make_packet()
        settings = config(
            resource(acceptance=0.000001, latency=31536000, review=525600, regression=1)
        )
        settings["policy"].update(
            prior_samples=1,
            wall_second_usd=1000000,
            review_minute_usd=1000000,
            regression_usd=1000000,
        )
        inputs = request(packet)
        extreme = observation()
        extreme.update(
            samples=1000000000,
            accepted=0,
            mean_latency_seconds=31536000,
            mean_review_minutes=525600,
            regressions=1000000000,
        )
        inputs["observations"] = [extreme]
        result = router.route(packet, settings, inputs)
        self.assertIn(result["status"], ("STOP", "ROUTED"))
        self.assertTrue(result["candidates"])

        def assert_finite(value):
            if isinstance(value, dict):
                for child in value.values():
                    assert_finite(child)
            elif isinstance(value, list):
                for child in value:
                    assert_finite(child)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                self.assertTrue(math.isfinite(value), value)

        assert_finite(result)
        json.dumps(result, allow_nan=False)

    def test_matched_observations_blend_with_prior_and_all_cost_components(self):
        packet = make_packet()
        settings = config(
            resource(
                api=1, latency=10, acceptance=0.8, churn=100, review=2, regression=0.1
            )
        )
        inputs = request(packet)
        inputs["observations"] = [observation()]
        result = router.route(packet, settings, inputs)
        row = result["candidates"][0]
        expected = {
            "acceptance_probability": 0.6,
            "latency_seconds": 6,
            "context_churn_tokens": 50,
            "review_minutes": 1,
            "regression_probability": 0.15,
        }
        for key, value in expected.items():
            self.assertAlmostEqual(row["estimates"][key], value)
        self.assertEqual(row["estimate_source"]["kind"], "prior_plus_observations")
        self.assertEqual(row["estimate_source"]["samples"], 5)
        self.assertEqual(
            row["cost_components"],
            {"api_usd": 1.025, "time_usd": 6, "review_usd": 1, "regression_usd": 1.5},
        )
        self.assertAlmostEqual(row["estimated_attempt_cost_usd"], 9.525)
        self.assertAlmostEqual(row["expected_cost_per_accepted_result_usd"], 15.875)

    def test_telemetry_only_matches_resource_task_class_and_exact_effort(self):
        packet = make_packet()
        settings = config(resource(acceptance=0.8, latency=10))
        for item in (
            observation(task_class="other-class"),
            observation(effort="high"),
            observation(resource_id="other-resource"),
        ):
            with self.subTest(observation=item):
                inputs = request(packet)
                inputs["observations"] = [item]
                row = router.route(packet, settings, inputs)["candidates"][0]
                self.assertEqual(
                    row["estimate_source"], {"kind": "configured_prior", "samples": 0}
                )
                self.assertEqual(row["estimates"]["acceptance_probability"], 0.8)
                self.assertEqual(row["estimates"]["latency_seconds"], 10)

    def test_stable_tie_breaking_is_independent_of_unordered_input_lists(self):
        packet = make_packet()
        settings = config(resource("zeta"), resource("alpha", provider="mistral"))
        inputs = request(packet)
        inputs["unavailable_providers"] = ["openai", "claude"]
        inputs["unavailable_resources"] = ["not-present-z", "not-present-a"]
        inputs["observations"] = [
            observation("zeta", "other"),
            observation("alpha", "other"),
        ]
        result = router.route(packet, settings, inputs)
        reordered_config, reordered_request = (
            copy.deepcopy(settings),
            copy.deepcopy(inputs),
        )
        reordered_config["providers"].reverse()
        reordered_config["resources"].reverse()
        for field in ("unavailable_providers", "unavailable_resources", "observations"):
            reordered_request[field].reverse()
        self.assertEqual(result["selected"]["resource_id"], "alpha")
        self.assertEqual(
            result, router.route(packet, reordered_config, reordered_request)
        )

    def test_route_and_record_do_not_modify_inputs_or_alias_saved_values(self):
        packet = make_packet()
        settings, inputs = config(), request(packet)
        preserved = copy.deepcopy((packet, settings, inputs))
        decision = router.route(packet, settings, inputs)
        saved = router.record(packet, settings, inputs)
        self.assertEqual((packet, settings, inputs), preserved)
        self.assertEqual(saved["decision"], decision)
        settings["resources"][0]["model"] = "Changed caller-owned model"
        inputs["task_class"] = "changed-class"
        packet["state"] = "BLOCKED"
        self.assertEqual(
            saved["inputs"], dict(zip(("packet", "config", "request"), preserved))
        )
        self.assertEqual(router.verify(saved), decision)

    def test_replay_detects_decision_or_saved_input_tampering(self):
        packet = make_packet()
        saved = router.record(packet, config(), request(packet))
        self.assertEqual(router.verify(saved), saved["decision"])
        for field, changed in (
            ("execution_authorized", True),
            ("decision_id", "0" * 64),
            ("reason_codes", ["FORGED"]),
        ):
            with self.subTest(field=field):
                forged = copy.deepcopy(saved)
                forged["decision"][field] = changed
                with self.assertRaisesRegex(ValueError, "does not reproduce"):
                    router.verify(forged)
        for section, field, changed in (
            ("config", "schema_version", "2.0"),
            ("request", "task_class", "changed-class"),
            ("packet", "state", "VERIFIED"),
        ):
            with self.subTest(section=section):
                forged = copy.deepcopy(saved)
                forged["inputs"][section][field] = changed
                with self.assertRaises(ValueError):
                    router.verify(forged)
        for malformed in (None, [], {"inputs": {}}, {**saved, "extra": True}):
            with self.subTest(malformed=type(malformed).__name__):
                with self.assertRaises(ValueError):
                    router.verify(malformed)


class RouterCommandLineTests(unittest.TestCase):
    def test_cli_validation_refuses_config_outside_native_foundation_bounds(self):
        for field, value in (("max_review_attempts", 8), ("failures_per_tier", 3)):
            settings = config()
            settings["policy"][field] = value
            bad_path = self.write_json("weakened-config.json", settings)
            self.assert_failure(self.cli("validate-config", bad_path))
        settings = config()
        settings["policy"]["risk_floor"]["high"] = 2
        bad_path = self.write_json("weakened-config.json", settings)
        self.assert_failure(self.cli("validate-config", bad_path))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.packet = make_packet()
        self.packet_path = self.write_json("packet.json", self.packet)
        self.config_path = self.write_json("config.json", config())
        self.request_path = self.write_json("request.json", request(self.packet))

    def write_json(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=self.directory,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def route_arguments(self, output):
        return (
            "route",
            self.packet_path,
            "--config",
            self.config_path,
            "--request",
            self.request_path,
            "--output",
            output,
        )

    def assert_failure(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Model routing failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_validates_routes_and_replays_an_immutable_record(self):
        sources = {
            path: path.read_bytes()
            for path in (self.packet_path, self.config_path, self.request_path)
        }
        checked = self.cli("validate-config", self.config_path)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("does not check live availability or credentials", checked.stdout)
        output = self.directory / "routing-record.json"
        routed = self.cli(*self.route_arguments(output))
        self.assertEqual(routed.returncode, 0, routed.stdout + routed.stderr)
        saved = wp.read_json(output)
        self.assertEqual(set(saved), {"inputs", "decision"})
        self.assertIs(saved["decision"]["execution_authorized"], False)
        verified = self.cli("verify", output)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual(json.loads(verified.stdout), saved["decision"])
        before = output.read_bytes()
        self.assert_failure(self.cli(*self.route_arguments(output)))
        self.assertEqual(output.read_bytes(), before)
        for path, original in sources.items():
            self.assertEqual(path.read_bytes(), original)

    def test_cli_refuses_output_aliases_without_modifying_any_input(self):
        preserved = {
            path: path.read_bytes()
            for path in (self.packet_path, self.config_path, self.request_path)
        }
        for output in preserved:
            with self.subTest(output=output.name):
                self.assert_failure(self.cli(*self.route_arguments(output)))
                for path, before in preserved.items():
                    self.assertEqual(path.read_bytes(), before)

    def test_cli_stop_is_recorded_and_replayable_without_execution(self):
        settings = config()
        settings["resources"][0]["enabled"] = False
        self.write_json("config.json", settings)
        output = self.directory / "stop-record.json"
        result = self.cli(*self.route_arguments(output))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        saved = wp.read_json(output)
        self.assertEqual(saved["decision"]["status"], "STOP")
        self.assertIs(saved["decision"]["execution_authorized"], False)
        self.assertEqual(self.cli("verify", output).returncode, 0)

    def test_cli_malformed_duplicate_and_nonfinite_json_leave_no_output(self):
        samples = (
            '{"schema_version":',
            '{"schema_version":"1.0","schema_version":"2.0"}',
            '{"binding":{"role":"worker","role":"reviewer"}}',
            '{"input_tokens":NaN}',
            '{"input_tokens":Infinity}',
            '{"input_tokens":1e999}',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.request_path.write_text(sample, encoding="utf-8")
                before = self.request_path.read_bytes()
                output = self.directory / "refused.json"
                self.assert_failure(self.cli(*self.route_arguments(output)))
                self.assertFalse(output.exists())
                self.assertEqual(self.request_path.read_bytes(), before)

    def test_cli_schema_errors_and_tampered_ledger_fail_cleanly(self):
        bad = config()
        del bad["policy"]["role_api_budget_usd"]
        bad_path = self.write_json("bad-config.json", bad)
        self.assert_failure(self.cli("validate-config", bad_path))
        inputs = request(self.packet)
        inputs["binding"]["contract_hash"] = "0" * 64
        self.write_json("request.json", inputs)
        output = self.directory / "refused.json"
        self.assert_failure(self.cli(*self.route_arguments(output)))
        self.assertFalse(output.exists())
        saved = router.record(self.packet, config(), request(self.packet))
        saved["decision"]["selected"]["model"] = "Forged model"
        tampered = self.write_json("tampered-record.json", saved)
        before = tampered.read_bytes()
        self.assert_failure(self.cli("verify", tampered))
        self.assertEqual(tampered.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
