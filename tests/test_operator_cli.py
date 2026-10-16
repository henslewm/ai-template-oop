"""Shell-only unit tests: all workflow operations use injected fakes."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.operator import OperatorService, OperatorView
from scripts import operator_cli


class FakeService(OperatorService):
    def __init__(self, *, error=None, view=None):
        self.calls = []
        self.error = error
        self.view = view or OperatorView(
            'Improve the operator start/resume experience', 'HELD',
            0.12, 0.03, 0.02, 8000, 2, 0.06,
            ('activation required', 'local image missing'),
            'Complete local activation, then resume --run',
        )

    def _result(self):
        if self.error is not None:
            raise self.error
        return self.view

    def start(self, objective):
        self.calls.append(('start', objective))
        return self._result()

    def status(self):
        self.calls.append(('status',))
        return self._result()

    def resume(self, *, run=False):
        self.calls.append(('resume', run))
        return self._result()


class OperatorCliTests(unittest.TestCase):
    def setUp(self):
        # Any accidental access to the real factory fails before opening it.
        self.factory = patch.object(
            operator_cli, 'open_service',
            side_effect=AssertionError('Tests must inject a fake service'),
        )
        self.factory_mock = self.factory.start()
        self.addCleanup(self.factory.stop)

    def invoke(self, argv, fake):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = operator_cli.main(argv, service=fake)
        self.factory_mock.assert_not_called()
        return code, output.getvalue(), errors.getvalue()

    def test_delegation_and_summary(self):
        objective = 'Improve the operator start/resume experience'
        for argv, expected in (
            ([objective], ('start', objective)),
            (['status'], ('status',)),
            (['resume'], ('resume', False)),
            (['resume', '--run'], ('resume', True)),
        ):
            with self.subTest(argv=argv):
                fake = FakeService()
                code, output, errors = self.invoke(argv, fake)
                self.assertEqual(code, 0)
                self.assertEqual(errors, '')
                self.assertEqual(fake.calls, [expected])
                for text in (
                    objective, 'HELD', 'Settled USD: 0.1200',
                    'Pending liability USD: 0.0300',
                    'Failed attempt cost USD: 0.0200', 'Context bytes: 8000',
                    'Accepted changes: 2', 'Cost per accepted change USD: 0.0600',
                    'activation required', 'local image missing',
                    'Next action: Complete local activation, then resume --run',
                ):
                    self.assertIn(text, output)

    def test_inspection_does_not_start_or_continue(self):
        for argv, expected in ((['status'], ('status',)),
                               (['resume'], ('resume', False))):
            with self.subTest(argv=argv):
                fake = FakeService()
                self.invoke(argv, fake)
                self.assertEqual(fake.calls, [expected])

    def test_unknown_accepted_cost_and_no_blockers(self):
        fake = FakeService()
        fake.view = replace(fake.view, accepted_changes=0,
                            cost_per_accepted_change_usd=None, blockers=())
        code, output, _ = self.invoke(['status'], fake)
        self.assertEqual(code, 0)
        self.assertIn('Cost per accepted change USD: unknown', output)
        self.assertIn('Blockers:\n  none', output)

    def test_invalid_arguments_do_not_delegate(self):
        for argv in ([], [''], ['   '], ['--run'], ['--unknown'],
                     ['status', '--run'], ['resume', 'yes'],
                     ['resume', '--run', 'extra'], ['unquoted', 'objective']):
            with self.subTest(argv=argv):
                fake = FakeService()
                code, output, errors = self.invoke(argv, fake)
                self.assertEqual(code, 2)
                self.assertEqual(output, '')
                self.assertEqual(fake.calls, [])
                self.assertIn('Pass one quoted objective', errors)
                self.assertEqual(len(errors.splitlines()), 1)
                self.assertNotIn('Traceback', errors)

    def test_service_errors_are_actionable_without_tracebacks(self):
        for argv in (['an objective'], ['status'], ['resume'], ['resume', '--run']):
            with self.subTest(argv=argv):
                fake = FakeService(error=RuntimeError('Local setup missing\nactivation required'))
                code, output, errors = self.invoke(argv, fake)
                self.assertEqual(code, 1)
                self.assertEqual(output, '')
                self.assertIn('Local setup missing activation required', errors)
                self.assertIn('Check local setup', errors)
                self.assertIn('start.ps1 status', errors)
                self.assertEqual(len(errors.splitlines()), 1)
                self.assertNotIn('Traceback', errors)

    def test_help_does_not_delegate(self):
        fake = FakeService()
        code, output, errors = self.invoke(['--help'], fake)
        self.assertEqual(code, 0)
        self.assertIn('Usage:', output)
        self.assertEqual(errors, '')
        self.assertEqual(fake.calls, [])

    def test_default_argv_still_uses_injected_service(self):
        fake = FakeService()
        with patch.object(sys, 'argv', ['operator_cli', 'resume']):
            code, _, errors = self.invoke(None, fake)
        self.assertEqual(code, 0)
        self.assertEqual(errors, '')
        self.assertEqual(fake.calls, [('resume', False)])


if __name__ == '__main__':
    unittest.main()
