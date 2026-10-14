#!/usr/bin/env python3
"""The one Ctrl+C policy for every scripts/*.py command line (ADR-072; docs/REFERENCE.md "CLI exit codes").

A CLI returns 0 for success, 1 for a handled refusal and 2 for a not-OK outcome itself; this
module adds only what is shared: an interrupt returns 130 without a traceback, whether it
arrives while the CLI is still loading or once it runs, and the few steps an interrupt must not
cut in half hold it until they finish.

A CLI imports this module before anything else, so at module level it imports only `sys`, which
the interpreter always has loaded (even under `python -S`): loading it opens no window in which
an interrupt could escape before `guard_startup` is installed. Everything else is imported
where it is used.
"""
from __future__ import annotations

import sys

INTERRUPTED = 130
MESSAGE = ("Interrupted. Records written before the interrupt are kept; "
           "check the ledger or output status before retrying.")


def report():
    """Say the command was interrupted, best-effort: a closed or broken stderr never changes 130."""
    try:
        print(MESSAGE, file=sys.stderr)
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


def guard_startup():
    """Map a Ctrl+C that arrives while a CLI is still importing, before `run` is reached, to 130.

    Called first in a CLI's `__main__` path, before its own imports. Nothing has been written at
    that point, so the process exits at once with no traceback; any other uncaught exception is
    left to the previous hook.
    """
    previous = sys.excepthook

    def hook(kind, value, traceback):
        if issubclass(kind, KeyboardInterrupt):
            import os
            report()
            os._exit(INTERRUPTED)
        previous(kind, value, traceback)

    sys.excepthook = hook


def run(main, *args):
    """Call a CLI entry point, returning its exit code, or INTERRUPTED on Ctrl+C.

    Owned work is stopped by its owner while the interrupt propagates: a check's process tree
    is ended and confirmed stopped by `acceptance.ProcessTree.own`, which refuses the run
    instead when it cannot confirm that. So an interrupt that reaches here has already been
    through that teardown. This reports and returns; it never writes, repairs or removes a
    ledger, report or evidence file.
    """
    try:
        return main(*args)
    except KeyboardInterrupt:
        report()
        return INTERRUPTED


class interrupts_held:
    """Hold a Ctrl+C that arrives inside the block and raise it once the block completes.

    For the few steps an interrupt must not split: a launched check reaching its owner, the
    owner confirming the check's tree stopped, and a ledger event or new output file being
    written whole. `with interrupts_held() as held` gives the list of held signals, so the block
    can see whether one arrived. If the block raises, that exception propagates and a held
    interrupt is dropped with it, so a refusal is never masked. Python raises KeyboardInterrupt
    only in the main thread and installs handlers only there; elsewhere, or when SIGINT is not
    Python's default handler (ignored, or replaced by an embedding program), the block runs
    unchanged.
    """

    def __enter__(self):
        import signal
        import threading
        self.held, self.previous = [], None
        if (threading.current_thread() is threading.main_thread()
                and signal.getsignal(signal.SIGINT) is signal.default_int_handler):
            self.previous = signal.signal(signal.SIGINT, lambda signum, frame: self.held.append(signum))
        return self.held

    def __exit__(self, kind, value, traceback):
        if self.previous is not None:
            import signal
            signal.signal(signal.SIGINT, self.previous)
        if kind is None and self.held:
            raise KeyboardInterrupt
        return False
