"""Trusted acceptance checks. Never supplied as writable worker input."""

import ast
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contracts.operator import OperatorService, OperatorView


class FakeService(OperatorService):
    def __init__(self):
        self.calls = []

    def view(self):
        return OperatorView(
            "test objective",
            "HELD",
            0.12,
            0.03,
            0.02,
            8000,
            0,
            None,
            ("test blocker",),
            "test next action",
        )

    def start(self, objective):
        self.calls.append(("start", objective))
        return self.view()

    def status(self):
        self.calls.append(("status",))
        return self.view()

    def resume(self, *, run=False):
        self.calls.append(("resume", run))
        return self.view()


class ShellChecks(unittest.TestCase):
    def test_shell_delegation(self):
        from contextlib import redirect_stdout
        from io import StringIO

        cli = importlib.import_module("scripts.operator_cli")
        cases = [
            (["status"], ("status",)),
            (["resume"], ("resume", False)),
            (["resume", "--run"], ("resume", True)),
            (
                ["Improve the operator start/resume experience"],
                ("start", "Improve the operator start/resume experience"),
            ),
        ]
        for argv, expected in cases:
            fake, output = FakeService(), StringIO()
            with redirect_stdout(output):
                result = cli.main(argv, service=fake)
            self.assertIn(result, (0, 1, 2))
            self.assertEqual(fake.calls, [expected])
            rendered = output.getvalue().lower()
            for text in (
                "test objective",
                "held",
                "test blocker",
                "test next action",
                "0.12",
                "0.03",
            ):
                self.assertIn(text, rendered)

    def test_shell_has_no_controller_or_io_access(self):
        source = Path("scripts/operator_cli.py").read_text()
        tree = ast.parse(source)
        allowed = {
            "argparse",
            "sys",
            "pathlib",
            "contracts.operator",
            "scripts.operator_service",
            "__future__",
            "dataclasses",
            "typing",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(n.name in allowed for n in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(
                    node.func.id, {"exec", "eval", "compile", "open", "__import__"}
                )

    def test_launcher_and_readme(self):
        launcher = Path("start.ps1").read_text().lower()
        for text in ("3.12", "venv", "operator_cli", "pip", "docker"):
            self.assertIn(text, launcher)
        self.assertNotIn("remove-item", launcher)
        self.assertNotIn("invoke-expression", launcher)
        readme = Path("README.md").read_text().lower()
        for text in ("start.ps1", "status", "resume", "--run", "windows_quickstart.md"):
            self.assertIn(text, readme)


if __name__ == "__main__":
    unittest.main()
