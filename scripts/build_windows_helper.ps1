param(
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [string]$Python,
    [string]$UvExecutable,
    [switch]$PrepareEnvironment,
    [switch]$InventoryOnly
)
$ErrorActionPreference = 'Stop'
# No elevation, PATH registration, execution-policy changes, firewall actions,
# or browser launch. WorkRoot must be outside the canonical source checkout.
function Get-LocalWorkspacePath([string]$Path) {
    # Only ordinary local drive paths are supported. No UNC/device/drive-relative
    # paths, ADS, short-name aliases or Win32 trailing-dot/space normalization.
    if ($Path -notmatch '^[A-Za-z]:[\\/]') { throw 'Workspace must be an absolute local drive path' }
    if ($Path.Substring(2).Contains(':') -or $Path.Contains('~') -or
        $Path -match '[. ]([\\/]|$)') { throw 'Workspace path alias is unsupported' }
    $Full = [IO.Path]::GetFullPath($Path).Replace('/', '\')
    $Root = [IO.Path]::GetPathRoot($Full)
    if ($Full.Length -gt $Root.Length) { $Full = $Full.TrimEnd('\') }
    $Volume = Get-Volume -DriveLetter $Root.Substring(0,1) -ErrorAction Stop
    $Drive = [IO.DriveInfo]::new($Root)
    if (-not $Volume -or $Volume.FileSystem -ne 'NTFS' -or $Drive.DriveType -ne 'Fixed') {
        throw 'Workspace requires a fixed local NTFS volume'
    }
    # Walk even missing leaves: an existing aliased ancestor is still unsafe.
    $Component = $Full
    while ($Component) {
        $Item = Get-Item -LiteralPath $Component -Force -ErrorAction SilentlyContinue
        if ($Item) {
            if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Workspace reparse/junction/symlink aliases are unsupported'
            }
            if (-not $Item.PSIsContainer) { throw 'Workspace ancestor must be a directory' }
        }
        $Component = Split-Path -Parent $Component
    }
    return $Full
}
$Source = Get-LocalWorkspacePath (Split-Path -Parent $PSScriptRoot)
$WorkRoot = Get-LocalWorkspacePath $WorkRoot
if ($WorkRoot.Equals($Source, [StringComparison]::OrdinalIgnoreCase) -or
    $WorkRoot.StartsWith($Source.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'WorkRoot must be outside source'
}
$Inventory = [ordered]@{
    OS = [Environment]::OSVersion.VersionString
    Architecture = $env:PROCESSOR_ARCHITECTURE
    Tools = @(Get-Command python,py,uv,powershell,iexpress,signtool -ErrorAction SilentlyContinue | Select-Object Name,Source)
    Python = $Python
    UV = $UvExecutable
}
$Inventory | ConvertTo-Json -Depth 4
if ($InventoryOnly) { exit 0 }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
if ($PrepareEnvironment) {
    if (-not $UvExecutable -or -not (Test-Path -LiteralPath $UvExecutable -PathType Leaf)) {
        throw 'Provide an existing or explicitly approved isolated uv executable; no global installation is performed'
    }
    $env:UV_CACHE_DIR = Join-Path $WorkRoot 'uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $WorkRoot 'python'
    $env:UV_PYTHON_BIN_DIR = Join-Path $WorkRoot 'bin'
    $Venv = Join-Path $WorkRoot 'venv'
    if (-not (Test-Path -LiteralPath $Venv)) {
        & $UvExecutable venv --python 3.11 --managed-python --no-project $Venv
        if ($LASTEXITCODE) { throw 'Isolated Python environment creation failed' }
    }
    $Python = Join-Path $Venv 'Scripts\python.exe'
    & $UvExecutable pip install --python $Python 'pyatv==0.18.0' 'PyInstaller==6.21.0' 'pytest==9.0.2'
    if ($LASTEXITCODE) { throw 'Isolated dependency install failed' }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Provide the isolated Python executable, or use PrepareEnvironment with approved uv'
}
& $Python (Join-Path $PSScriptRoot 'build_windows_helper.py') --inventory
if ($LASTEXITCODE) { throw 'Python inventory failed' }
Push-Location $Source
try {
    & $Python -m pytest -q tests/test_windows_source.py tests/test_windows_installer.py tests/test_windows_native.py
    if ($LASTEXITCODE) { throw 'Windows fixture/source tests failed' }
    $Output = Join-Path $WorkRoot ('build-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    & $Python (Join-Path $PSScriptRoot 'build_windows_helper.py') --output $Output
    if ($LASTEXITCODE) { throw 'Windows package build failed' }
} finally {
    Pop-Location
}
