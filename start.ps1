# Native commands are invoked with argument arrays, never evaluated as code.
$ErrorActionPreference = 'Stop'
$forwardArgs = @($args)
$root = $PSScriptRoot
$result = 1
$pushed = $false

try {
    Push-Location -LiteralPath $root
    $pushed = $true
    $venv = Join-Path $root '.venv'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    $created = $false

    if (-not (Test-Path -LiteralPath $venv)) {
        $versionProbe = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'
        $bootstrap = $null
        $bootstrapArgs = @()
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -I -B -c $versionProbe 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $bootstrap = 'py'
                $bootstrapArgs = @('-3')
            } else {
                & py -3.12 -I -B -c $versionProbe 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $bootstrap = 'py'
                    $bootstrapArgs = @('-3.12')
                }
            }
        }
        if (-not $bootstrap -and (Get-Command python -ErrorAction SilentlyContinue)) {
            & python -I -B -c $versionProbe 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $bootstrap = 'python' }
        }
        if (-not $bootstrap) {
            throw 'Install Python 3.12+ with the py launcher or put python on PATH, then retry.'
        }
        & $bootstrap @bootstrapArgs -I -B -m venv $venv
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not create .venv. Check Python venv support and repository permissions.'
        }
        $created = $true
    }

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw 'Existing .venv has no Scripts\python.exe. Repair it explicitly with Python 3.12+; it was not replaced.'
    }
    $verifyEnvironment = @'
import pathlib, site, sys
venv = pathlib.Path(sys.argv[1]).resolve()
expected = pathlib.Path(sys.argv[2]).resolve()
config = {}
for line in (venv / 'pyvenv.cfg').read_text().splitlines():
    key, sep, value = line.partition('=')
    if sep:
        config[key.strip().lower()] = value.strip().lower()
valid = (
    sys.version_info >= (3, 12)
    and sys.prefix != sys.base_prefix
    and pathlib.Path(sys.prefix).resolve() == venv
    and pathlib.Path(sys.executable).resolve() == expected
    and config.get('include-system-site-packages') == 'false'
    and not site.ENABLE_USER_SITE
)
raise SystemExit(0 if valid else 1)
'@
    & $venvPython -I -B -c $verifyEnvironment $venv $venvPython
    if ($LASTEXITCODE -ne 0) {
        throw '.venv must use Python 3.12+ and be isolated (no system site packages). Repair it explicitly; it was not replaced.'
    }

    if ($created) {
        & $venvPython -I -B -m pip install -e '.[dev]'
        if ($LASTEXITCODE -ne 0) {
            throw 'Development dependency installation failed. Resolve the pip error and explicitly install .[dev] into .venv before retrying.'
        }
    }

    # Check the actual declared constraints, including pinned versions; do not
    # silently install or upgrade anything in an existing environment.
    $verifyDependencies = @'
import importlib.metadata as metadata
import pathlib, sys, tomllib
from pip._vendor.packaging.requirements import Requirement
project = tomllib.loads((pathlib.Path(sys.argv[1]) / 'pyproject.toml').read_text())['project']
dev = project.get('optional-dependencies', {}).get('dev')
if not dev:
    raise SystemExit('No declared project dev dependencies found.')
requirements = list(project.get('dependencies', [])) + list(dev)
for text in requirements:
    requirement = Requirement(text)
    if requirement.marker and not requirement.marker.evaluate({'extra': 'dev'}):
        continue
    version = metadata.version(requirement.name)
    if not requirement.specifier.contains(version, prereleases=True):
        raise SystemExit(f'{requirement.name} {version} does not satisfy {requirement.specifier}')
'@
    & $venvPython -I -B -c $verifyDependencies $root
    if ($LASTEXITCODE -ne 0) {
        throw 'Declared development dependencies are missing or incompatible. Explicitly run .\.venv\Scripts\python.exe -m pip install -e ".[dev]", then retry.'
    }
    & $venvPython -I -B -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw 'The existing environment has dependency conflicts. Resolve the pip check findings explicitly, then retry.'
    }

    $execution = $false
    if ($forwardArgs.Count -eq 1) {
        $objective = [string]$forwardArgs[0]
        $execution = ($objective.Trim().Length -gt 0 -and
            $objective -cne 'status' -and $objective -cne 'resume' -and
            -not $objective.StartsWith('-'))
    } elseif ($forwardArgs.Count -eq 2) {
        $execution = ($forwardArgs[0] -ceq 'resume' -and $forwardArgs[1] -ceq '--run')
    }
    if ($execution) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw 'Install Git and make it available on PATH before running work.'
        }
        & git rev-parse --show-toplevel | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Run from a valid Git checkout before running work.' }
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
            throw 'Install GitHub CLI (gh) and make it available on PATH before running work; see docs/workflow-migration/LIVE_PILOT.md.'
        }
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw 'Install Docker Desktop and make docker available on PATH before running work.'
        }
        & docker info | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for its engine, then retry.' }
        if ([string]::IsNullOrWhiteSpace($env:WORKFLOW_TEST_IMAGE)) {
            throw 'Set WORKFLOW_TEST_IMAGE to the verified, already local worker image; see the Windows quickstart.'
        }
        & docker image inspect -- $env:WORKFLOW_TEST_IMAGE | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'WORKFLOW_TEST_IMAGE is not available locally. Complete the verified image setup in the Windows quickstart; this launcher never pulls images.'
        }
    }

    # Local activation, provider keys and budget eligibility belong to the
    # trusted facade. Inspection does not require a key or Docker.
    & $venvPython -B -m scripts.operator_cli @forwardArgs
    $result = $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine(('Launcher error: ' + $_.Exception.Message))
    $result = 1
} finally {
    if ($pushed) { Pop-Location }
}
exit $result
