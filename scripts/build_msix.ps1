<#
  Package the PyInstaller build (dist\windows\SmartCalender) as an MSIX for the
  Microsoft Store. Run on Windows after scripts\build_windows.bat.

  Required (from Partner Center > your app > Product identity):
    $env:MSIX_IDENTITY_NAME            e.g. 12345Deskhab.SmartCalender
    $env:MSIX_PUBLISHER                e.g. CN=ABCDEF12-3456-7890-ABCD-EF1234567890
    $env:MSIX_PUBLISHER_DISPLAY_NAME   e.g. Deskhab
  Optional:
    $env:APP_VERSION                   e.g. 1.3.0  (Store needs a.b.c.0)

  The Store signs the package itself, so no certificate is needed for submission.
  Output: dist\windows\SmartCalender-<version>-x64.msix
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AppDir = Join-Path $Root "dist\windows\SmartCalender"
if (-not (Test-Path (Join-Path $AppDir "SmartCalender.exe"))) {
  throw "Build not found at $AppDir. Run scripts\build_windows.bat first."
}

foreach ($name in "MSIX_IDENTITY_NAME", "MSIX_PUBLISHER", "MSIX_PUBLISHER_DISPLAY_NAME") {
  if (-not [Environment]::GetEnvironmentVariable($name)) {
    throw "$name is not set. Copy it from Partner Center > Product identity."
  }
}

$version = $env:APP_VERSION
if (-not $version) {
  $line = Select-String -Path (Join-Path $Root "scripts\build_windows.bat") -Pattern '^set VERSION=(.+)$' | Select-Object -First 1
  $version = $line.Matches[0].Groups[1].Value.Trim()
}
$parts = $version.Split(".")
while ($parts.Count -lt 3) { $parts += "0" }
$msixVersion = "{0}.{1}.{2}.0" -f $parts[0], $parts[1], $parts[2]   # Store requires revision 0

$Stage = Join-Path $Root "build\msix"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage | Out-Null
Copy-Item -Path (Join-Path $AppDir "*") -Destination $Stage -Recurse
New-Item -ItemType Directory -Path (Join-Path $Stage "Assets") | Out-Null
Copy-Item -Path (Join-Path $Root "assets\msix\*.png") -Destination (Join-Path $Stage "Assets")

$manifest = Get-Content (Join-Path $Root "packaging\msix\AppxManifest.template.xml") -Raw
$esc = { param($s) [System.Security.SecurityElement]::Escape($s) }
$manifest = $manifest.Replace("{{IDENTITY_NAME}}", (& $esc $env:MSIX_IDENTITY_NAME))
$manifest = $manifest.Replace("{{PUBLISHER}}", (& $esc $env:MSIX_PUBLISHER))
$manifest = $manifest.Replace("{{PUBLISHER_DISPLAY_NAME}}", (& $esc $env:MSIX_PUBLISHER_DISPLAY_NAME))
$manifest = $manifest.Replace("{{VERSION}}", $msixVersion)
Set-Content -Path (Join-Path $Stage "AppxManifest.xml") -Value $manifest -Encoding UTF8

# Locate makeappx.exe from the newest Windows SDK
$sdk = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Directory |
  Where-Object { Test-Path (Join-Path $_.FullName "x64\makeappx.exe") } |
  Sort-Object Name -Descending | Select-Object -First 1
if (-not $sdk) { throw "makeappx.exe not found. Install the Windows 10/11 SDK." }
$makeappx = Join-Path $sdk.FullName "x64\makeappx.exe"

$out = Join-Path $Root ("dist\windows\SmartCalender-{0}-x64.msix" -f $msixVersion)
if (Test-Path $out) { Remove-Item $out -Force }
& $makeappx pack /d $Stage /p $out /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }
Write-Host "MSIX ready: $out (version $msixVersion)"
Write-Host "Upload it in Partner Center > Packages. The Store signs it for you."
