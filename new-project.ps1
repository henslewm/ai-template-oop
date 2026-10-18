param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$')]
    [string]$Slug
)

$ErrorActionPreference = 'Stop'

if ($Slug.Length -gt 64) {
    throw 'Slug must be at most 64 characters.'
}
if ($PWD.Provider.Name -ne 'FileSystem') {
    throw 'Run this command from a filesystem directory.'
}

$PythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $PythonCommand) {
    throw 'Python is required and must be available as python on PATH.'
}

$WorkingDirectory = $PWD.Path
$Specification = Join-Path $WorkingDirectory ($Slug + '.request.json')
$Destination = Join-Path $WorkingDirectory $Slug
$Intake = Join-Path (Join-Path $PSScriptRoot 'tools') 'project_intake.py'

if (-not (Test-Path -LiteralPath $Specification -PathType Leaf)) {
    & $PythonCommand.Source -B $Intake draft $Specification --slug $Slug
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create the intake questionnaire.'
    }

    Write-Host "Edit $Specification, then run this command again."
    $Editor = $env:EDITOR
    if (-not $Editor -and [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $Editor = 'notepad.exe'
    }
    if ($Editor) {
        Start-Process -FilePath $Editor -ArgumentList ('"{0}"' -f $Specification)
    }
    else {
        Invoke-Item -LiteralPath $Specification
    }
    return
}

$Request = Get-Content -LiteralPath $Specification -Raw | ConvertFrom-Json
if ($Request.slug -cne $Slug) {
    throw "The request slug must remain '$Slug'."
}

$ReviewOutput = & $PythonCommand.Source -B $Intake review $Specification
if ($LASTEXITCODE -ne 0) {
    throw 'Review failed; resolve the intake errors before continuing.'
}
$ReviewJson = $ReviewOutput -join [Environment]::NewLine
Write-Output $ReviewJson
$Review = $ReviewJson | ConvertFrom-Json
if (-not $Review.ready) {
    throw 'Resolve all open questions in the request, then run this command again.'
}

$Fingerprint = Read-Host 'Enter the review fingerprint shown above to acknowledge it'
$ReviewedBy = Read-Host 'Enter your name as the reviewer'
& $PythonCommand.Source -B $Intake generate $Specification $Destination --accept $Fingerprint --reviewed-by $ReviewedBy
if ($LASTEXITCODE -ne 0) {
    throw 'Generation failed; preserve any partial output and inspect the error.'
}

$VirtualEnvironment = Join-Path $Destination '.venv'
& $PythonCommand.Source -m venv $VirtualEnvironment
if ($LASTEXITCODE -ne 0) {
    throw 'Virtual environment creation failed; preserve the generated project.'
}

if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
    $EnvironmentPython = Join-Path (Join-Path $VirtualEnvironment 'Scripts') 'python.exe'
}
else {
    $EnvironmentPython = Join-Path (Join-Path $VirtualEnvironment 'bin') 'python'
}

Push-Location $Destination
try {
    & $EnvironmentPython -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Development dependency installation failed; preserve the generated project.'
    }
    & $EnvironmentPython -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw 'Generated project tests failed; preserve the generated project.'
    }
}
finally {
    Pop-Location
}
