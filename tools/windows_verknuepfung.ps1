# ---------------------------------------------------------------------------
# PollySort — Startmenü- und Desktop-Verknüpfung (Windows)
#
# Gemeinsam genutzt von install.ps1, install.sh (Git-Bash) und den Deinstallern,
# damit es genau EINE Stelle gibt, die Verknüpfungen anlegt oder entfernt.
#
#   tools\windows_verknuepfung.ps1 -Ziel <...\pollysort-app.exe> -Icon <...\pollysort.ico>
#   tools\windows_verknuepfung.ps1 -Entfernen
#   ... -DryRun     nur zeigen, was passieren würde
#
# Nur für den aktuellen Benutzer (eigenes Startmenü, eigener Desktop) — keine
# Administratorrechte. Entfernt werden ausschließlich Verknüpfungen namens
# „PollySort", die wirklich auf pollysort-app zeigen; alles andere bleibt liegen.
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [string]$Ziel,
    [string]$Icon,
    [switch]$Entfernen,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Ok   ($m) { Write-Host "   [ok] $m"  -ForegroundColor Green }
function Info ($m) { Write-Host "   $m" }
function Warn ($m) { Write-Host "   [!] $m"   -ForegroundColor Yellow }

# GetFolderPath kennt auch umgeleitete Ordner (z. B. den Desktop in OneDrive).
$orte = @(
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'PollySort.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop'))  'PollySort.lnk')
)
$shell = New-Object -ComObject WScript.Shell

if ($Entfernen) {
    foreach ($o in $orte) {
        if (-not (Test-Path -LiteralPath $o)) { continue }
        $lnk = $shell.CreateShortcut($o)
        if ($lnk.TargetPath -notmatch 'pollysort-app') {
            Warn "Gehoert nicht zu PollySort, bleibt liegen: $o"
            continue
        }
        if ($DryRun) { Info "[dry-run] wuerde entfernen: $o"; continue }
        Remove-Item -LiteralPath $o -Force
        Ok "Verknuepfung entfernt: $o"
    }
    exit 0
}

if ($DryRun) {
    foreach ($o in $orte) { Info "[dry-run] wuerde anlegen: $o -> $Ziel" }
    exit 0
}
if (-not $Ziel -or -not (Test-Path -LiteralPath $Ziel)) {
    Warn "pollysort-app nicht gefunden ($Ziel) - keine Verknuepfung angelegt."
    exit 1
}
foreach ($o in $orte) {
    $lnk = $shell.CreateShortcut($o)
    $lnk.TargetPath = $Ziel
    $lnk.WorkingDirectory = $env:USERPROFILE
    if ($Icon -and (Test-Path -LiteralPath $Icon)) { $lnk.IconLocation = "$Icon,0" }
    $lnk.Description = 'PollySort - lernender Dokumenten-Archivar'
    $lnk.Save()
    Ok "Verknuepfung angelegt: $o"
}
exit 0
