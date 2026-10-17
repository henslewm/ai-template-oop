# ai-template-oop

Contract-first application template with a bounded operator onboarding shell.

## Start from PowerShell

From the repository root:

```powershell
.\start.ps1 "Improve the operator start/resume experience"
.\start.ps1 status
.\start.ps1 resume
```

The quoted objective uses the approved bounded preset, not arbitrary project
execution. Limits remain **$1 per task / $5 per pilot**. Before running work,
complete the [local pilot activation](docs/workflow-migration/LIVE_PILOT.md#bootstrap-and-operation)
and provider-key setup, start Docker Desktop,
and set `WORKFLOW_TEST_IMAGE` to the already verified local worker image.
Python 3.12+ and Git must be installed. The launcher creates an isolated
`.venv` and installs declared development dependencies only when it is absent;
an existing environment is checked, never replaced or automatically repaired.

`status` and bare `resume` inspect existing records without paid calls; neither
requires Docker or a provider key. To explicitly continue eligible work, use
`.\start.ps1 resume --run`. Execution still requires local activation, key,
image and budget eligibility; the trusted service enforces these gates.

The compact handoff shows the objective, progress, settled/pending spend,
failed-attempt cost, context bytes, accepted-change cost, blockers and next
action. Preserve that summary when handing work to another session.

See the [Windows quickstart](docs/workflow-migration/WINDOWS_QUICKSTART.md)
for detailed setup and offline verification, including disposable workers and
independent acceptance. See [M6 operations](docs/workflow-migration/M6_OPERATIONS.md)
and [verification limits](docs/workflow-migration/M6_CLOSEOUT.md) for the
foundation's operational reference.

## Demo and architecture reference

The separate Tk/SQLite demo runs with `python main.py --mock` (demo/demo1234)
or `python main.py` (register first); it requires Tk. Architecture references:
[session boundaries and rules](CLAUDE.md), [contracts](contracts/), and
[composition root](src/container/wiring.py). The operator shell only parses
and displays; its trusted service owns workflow I/O.
