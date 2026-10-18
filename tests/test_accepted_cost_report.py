from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.accepted_cost_report import main, summarize


def activity(category, outcome, cost):
    return {"category": category, "outcome": outcome, "cost_usd": cost}


def side(accepted, implementation, integration, *activities):
    return {
        "accepted": accepted,
        "activities": [
            activity("implementation", "accepted", implementation),
            *activities,
            activity("integration", "accepted", integration),
        ],
    }


class AcceptedCostReportTests(unittest.TestCase):
    def record(self):
        return {
            "version": 1,
            "cohort": "matched-maintenance-tasks-2026-10",
            "provenance": {"kind": "real", "evidence_ref": "pilot-ledger:task-set-1"},
            "tasks": [
                {
                    "id": "task-1",
                    "baseline": side(
                        True,
                        10,
                        2,
                        activity("review", "failed", 1),
                        activity("review", "accepted", 2),
                    ),
                    "pilot": side(
                        True,
                        4,
                        1,
                        activity("review", "failed", 0.5),
                        activity("review", "accepted", 1),
                    ),
                },
                {
                    "id": "task-2",
                    "baseline": side(False, 3, 1),
                    "pilot": side(False, 2, 0.5),
                },
            ],
        }

    def test_matched_report_counts_failures_and_integration(self):
        report = summarize(self.record())
        self.assertEqual(report["task_ids"], ["task-1", "task-2"])
        self.assertEqual(report["baseline"]["accepted_results"], 1)
        self.assertEqual(report["baseline"]["total_cost_usd"], "19")
        self.assertEqual(report["baseline"]["failed_attempt_cost_usd"], "1")
        self.assertEqual(report["baseline"]["integration_cost_usd"], "3")
        self.assertEqual(report["pilot"]["total_cost_usd"], "9")
        self.assertEqual(report["pilot"]["failed_attempt_cost_usd"], "0.5")
        self.assertEqual(report["pilot"]["integration_cost_usd"], "1.5")
        self.assertEqual(
            report["comparison"]["savings_per_accepted_result_usd"], "10"
        )
        self.assertTrue(report["provenance"]["non_fixture_declared"])
        self.assertEqual(report["provenance"]["status"], "declared_not_verified")

    def test_unknown_cost_is_not_treated_as_zero(self):
        record = self.record()
        record["tasks"][0]["pilot"]["activities"][0]["cost_usd"] = None
        report = summarize(record)
        self.assertIsNone(report["pilot"]["total_cost_usd"])
        self.assertIsNone(report["pilot"]["cost_per_accepted_result_usd"])
        self.assertIsNone(report["comparison"]["savings_per_accepted_result_usd"])
        self.assertEqual(report["pilot"]["unknown_cost_items"], 1)
        self.assertEqual(report["pilot"]["integration_cost_usd"], "1.5")

    def test_no_accepted_results_has_unknown_cost_per_result(self):
        record = self.record()
        for task in record["tasks"]:
            task["baseline"]["accepted"] = False
        report = summarize(record)
        self.assertEqual(report["baseline"]["accepted_results"], 0)
        self.assertIsNone(report["baseline"]["cost_per_accepted_result_usd"])
        self.assertIsNone(report["comparison"]["savings_percent"])

    def test_fixture_provenance_cannot_qualify_as_real_measurement(self):
        record = self.record()
        record["provenance"]["kind"] = "fixture"
        report = summarize(record)
        self.assertFalse(report["provenance"]["non_fixture_declared"])

    def test_requires_explicit_integration_cost_for_each_arm(self):
        record = self.record()
        record["tasks"][0]["pilot"]["activities"].pop()
        with self.assertRaisesRegex(ValueError, "explicitly record integration cost"):
            summarize(record)

    def test_rejects_duplicate_tasks_and_negative_costs(self):
        record = self.record()
        record["tasks"][1]["id"] = "task-1"
        with self.assertRaisesRegex(ValueError, "duplicate task id"):
            summarize(record)

        record = self.record()
        record["tasks"][0]["pilot"]["activities"][0]["cost_usd"] = -1
        with self.assertRaisesRegex(ValueError, "non-negative"):
            summarize(record)

    def test_rejects_boolean_costs_and_malformed_categories(self):
        record = self.record()
        record["tasks"][0]["pilot"]["activities"][0]["cost_usd"] = True
        with self.assertRaisesRegex(ValueError, "number or null"):
            summarize(record)

        record = self.record()
        record["tasks"][0]["pilot"]["activities"][0]["category"] = []
        with self.assertRaisesRegex(ValueError, "unknown activity category"):
            summarize(record)

    def test_cli_emits_report_bound_to_exact_manifest_bytes(self):
        record = self.record()
        raw = json.dumps(record).encode()
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "measurement.json"
            manifest.write_bytes(raw)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([str(manifest)]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["manifest_sha256"], sha256(raw).hexdigest())
        self.assertEqual(report["pilot"]["cost_per_accepted_result_usd"], "9")


if __name__ == "__main__":
    unittest.main()
