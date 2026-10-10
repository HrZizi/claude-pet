# Smoke-tests the Windows release artifacts the way a user would. Safe to run on a machine that already has
# Claude Pet installed: it installs into a scratch folder, registers nothing and never touches your hooks.
#
#   powershell -File scripts/smoke_test.ps1 -Dir dist [-Version 0.1.1]
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [string]$Version = ""
)
$ErrorActionPreference = "Stop"
$script:fail = 0
function Check($name, [bool]$ok) {
    if ($ok) { "  PASS  $name" } else { "  FAIL  $name"; $script:fail++ }
}
function ContainsText([string]$folder, [string[]]$needles) {
    foreach ($f in Get-ChildItem $folder -Recurse -File) {
        $s = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes($f.FullName))
        foreach ($n in $needles) { if ($s.Contains($n)) { return "$($f.Name) contains '$n'" } }
    }
    return ""
}

$zip = Get-ChildItem $Dir -Filter "ClaudePet-*-windows-portable.zip" | Select-Object -First 1
$setup = Get-ChildItem $Dir -Filter "ClaudePet-Setup-*.exe" | Select-Object -First 1
Check "portable zip present" ($null -ne $zip)
Check "installer present" ($null -ne $setup)
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("cp-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory $scratch | Out-Null
$personal = @($env:USERPROFILE, $env:USERPROFILE.Replace("\", "/"), "$env:USERNAME\AppData")

"== portable zip =="
Expand-Archive $zip.FullName "$scratch\portable"
$p = "$scratch\portable\ClaudePet"
Check "has ClaudePet.exe, claude-pet-cli.exe, portable.flag" ((Test-Path "$p\ClaudePet.exe") -and (Test-Path "$p\claude-pet-cli.exe") -and (Test-Path "$p\portable.flag"))
$v = (& "$p\claude-pet-cli.exe" --version).Trim()
Check "cli reports a version ($v)" ($v -match '^\d+\.\d+\.\d+$')
if ($Version) { Check "version is $Version" ($v -eq $Version) }
Check "keeps its data beside the exe" ((& "$p\claude-pet-cli.exe" doctor | Out-String) -match [regex]::Escape("$p\data"))
Check "built-in sprite packs load (claude, eevee, bulbasaur)" ((& "$p\claude-pet-cli.exe" pack list | Out-String) -match "claude\s.*built-in(?s).*eevee.*built-in(?s).*bulbasaur.*built-in")
$gui = Start-Process "$p\ClaudePet.exe" -ArgumentList "--demo" -PassThru
Start-Sleep 5
Check "ClaudePet.exe --demo starts and keeps running" (-not $gui.HasExited)
if (-not $gui.HasExited) { $gui | Stop-Process -Force }
$leak = ContainsText $p $personal
Check "no personal paths inside the build ($leak)" ($leak -eq "")

"== installer =="
$d = "$scratch\Install Test"
$proc = Start-Process $setup.FullName -ArgumentList "--silent", "--dir", "`"$d`"", "--no-connect", "--no-launch", "--no-register", "--no-start-menu" -Wait -PassThru
Check "silent install exits 0" ($proc.ExitCode -eq 0)
Check "installed files + uninstaller" ((Test-Path "$d\ClaudePet.exe") -and (Test-Path "$d\claude-pet-cli.exe") -and (Test-Path "$d\ClaudePet-Uninstall.exe"))
Check "no portable.flag in an installed copy" (-not (Test-Path "$d\portable.flag"))
Check "installed cli runs" ((& "$d\claude-pet-cli.exe" --version).Trim() -eq $v)
Check "installed build finds its built-in packs" ((& "$d\claude-pet-cli.exe" pack list | Out-String) -match "bulbasaur")
$null = Start-Process "$d\ClaudePet-Uninstall.exe" -ArgumentList "--uninstall", "--silent", "--keep-hooks" -Wait -PassThru
$gone = $false
foreach ($i in 1..30) { if (-not (Test-Path $d)) { $gone = $true; break }; Start-Sleep -Milliseconds 500 }
Check "uninstall removes the folder" $gone

Remove-Item $scratch -Recurse -Force -ErrorAction SilentlyContinue
""
if ($script:fail -eq 0) { "ALL CHECKS PASSED" } else { "$($script:fail) CHECK(S) FAILED"; exit 1 }
