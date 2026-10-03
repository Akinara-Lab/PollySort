# ---------------------------------------------------------------------------
# PollySort — Deinstallation für Windows (PowerShell)
#
#   .\uninstall.ps1              nur die Anwendung entfernen (Befehle, PATH-Eintrag, Verknüpfungen)
#   .\uninstall.ps1 -Alles       zusätzlich die globale Ablage ~/.pollysort löschen
#   .\uninstall.ps1 -DryRun      nur zeigen, was passieren würde
#
# WAS NIE ANGERÜHRT WIRD — unter keiner Option:
#   * deine Projektordner und die einsortierten Dateien darin
#   * die versteckten `.honig`-Ordner in den Projekten. Darin liegt unter anderem
#     `papierkorb/` — die Quarantäne, die noch echte Dateien enthalten kann, die du
#     zwar aussortiert, aber nie endgültig gelöscht hast.
#
# Das Skript listet diese Ordner am Ende auf, damit du selbst entscheiden kannst.
# Ein Deinstaller, der ungefragt Nutzerdaten mitnimmt, ist ein Datenverlust mit
# gutem Gewissen — und das Grundprinzip von PollySort ist: nie löschen.
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [switch]$Alles,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Say  ($m) { Write-Host "`n[BEE] $m" -ForegroundColor Yellow }
function Ok   ($m) { Write-Host "   [ok] $m"  -ForegroundColor Green }
function Info ($m) { Write-Host "   $m" }
function Warn ($m) { Write-Host "   [!] $m"   -ForegroundColor Yellow }
function Fail ($m) { Write-Host "   [X] $m"   -ForegroundColor Red }

function Has-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# Native Programme schreiben Warnungen und Hinweise nach stderr. Mit
# $ErrorActionPreference = 'Stop' macht PowerShell daraus einen Abbruch: Ein
# 'pip show' fuer ein nicht installiertes Paket wuerde das Skript mittendrin
# beenden. Deshalb laufen ALLE Aufrufe fremder Programme durch diesen Helfer,
# der stderr einsammelt und nur den Exit-Code weiterreicht.
function Invoke-Tool {
    param([Parameter(Mandatory)][string]$Exe, [string[]]$Argumente = @())
    $vorher = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $ausgabe = (& $Exe @Argumente 2>&1 | Out-String)
        $code = $LASTEXITCODE
    }
    catch {
        $ausgabe = "$_"
        $code = 1
    }
    finally { $ErrorActionPreference = $vorher }
    return [pscustomobject]@{ Ausgabe = $ausgabe; Code = $code }
}

Say 'PollySort deinstallieren'
if ($DryRun) { Warn 'Trockenlauf - es wird nichts veraendert.' }

# --------------------------------------------------------------------------- #
# 0) Vorher merken, welche Projekte es gibt (die Registry wird ggf. geloescht)
# --------------------------------------------------------------------------- #
$home_dir = $env:POLLYSORT_HOME
if (-not $home_dir) { $home_dir = $env:BEEHIVE_HOME }
if (-not $home_dir) { $home_dir = Join-Path $env:USERPROFILE '.pollysort' }
$legacy_dir = Join-Path $env:USERPROFILE '.beehive'

$projekte = @()
$reg = Join-Path $home_dir 'projects.txt'
if (Test-Path $reg) {
    $projekte = Get-Content $reg -ErrorAction SilentlyContinue |
                Where-Object { $_ -and (Test-Path $_) }
}

# --------------------------------------------------------------------------- #
# 1) Die Anwendung entfernen
# --------------------------------------------------------------------------- #
Say 'Entferne die Anwendung ...'
$entfernt = $false

if (Has-Command 'uv') {
    if ((Invoke-Tool 'uv' @('tool', 'list')).Ausgabe -match 'pollysort') {
        if (-not $DryRun) { Invoke-Tool 'uv' @('tool', 'uninstall', 'pollysort') | Out-Null }
        Ok 'per uv entfernt'
        $entfernt = $true
    }
}
if (Has-Command 'pipx') {
    if ((Invoke-Tool 'pipx' @('list', '--short')).Ausgabe -match 'pollysort') {
        if (-not $DryRun) { Invoke-Tool 'pipx' @('uninstall', 'pollysort') | Out-Null }
        Ok 'per pipx entfernt'
        $entfernt = $true
    }
}
foreach ($c in @('py', 'python', 'python3')) {
    if (-not (Has-Command $c)) { continue }
    $zeigt = Invoke-Tool $c @('-m', 'pip', 'show', 'pollysort')
    if ($zeigt.Code -eq 0 -and $zeigt.Ausgabe -match 'Name:\s*pollysort') {
        if (-not $DryRun) {
            Invoke-Tool $c @('-m', 'pip', 'uninstall', '-y', 'pollysort') | Out-Null
        }
        Ok "per pip entfernt ($c)"
        $entfernt = $true
    }
    break
}
if (-not $entfernt) { Info 'Keine installierte Version gefunden (vielleicht schon entfernt).' }

# Verknuepfungen (Startmenue + Desktop) und was nur die Anwendung selbst angelegt hat:
# das Symbol und das Fensterprofil. Beides enthaelt keine Nutzerdaten.
Say 'Entferne Verknuepfungen ...'
& (Join-Path $PSScriptRoot 'tools\windows_verknuepfung.ps1') -Entfernen -DryRun:$DryRun
foreach ($rest in @((Join-Path $home_dir 'pollysort.ico'), (Join-Path $home_dir 'fenster'))) {
    if (-not (Test-Path -LiteralPath $rest)) { continue }
    if ($DryRun) { Info "[dry-run] wuerde entfernen: $rest"; continue }
    Remove-Item -LiteralPath $rest -Recurse -Force -ErrorAction SilentlyContinue
    Ok "entfernt: $rest"
}

# --------------------------------------------------------------------------- #
# 2) PATH-Eintrag zuruecknehmen
# --------------------------------------------------------------------------- #
Say 'Raeume den PATH auf ...'
$binDir = Join-Path $env:USERPROFILE '.local\bin'
$aktuell = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $aktuell) { $aktuell = '' }
$teile = $aktuell -split ';' | Where-Object { $_ -ne '' }

# Nur entfernen, wenn dort auch wirklich nichts anderes mehr liegt: Der Ordner
# ~/.local/bin gehoert uv und pipx gemeinsam, nicht PollySort allein.
$treffer = $teile | Where-Object { $_.TrimEnd('\') -ieq $binDir.TrimEnd('\') }
if (-not $treffer) {
    Info 'Kein von uns gesetzter PATH-Eintrag gefunden.'
}
elseif ((Test-Path $binDir) -and @(Get-ChildItem $binDir -File -ErrorAction SilentlyContinue).Count -gt 0) {
    Warn "PATH-Eintrag bleibt: in '$binDir' liegen noch andere Programme."
}
elseif ($DryRun) {
    Info "[dry-run] wuerde '$binDir' aus dem Benutzer-PATH nehmen"
}
else {
    $neu = ($teile | Where-Object { $_.TrimEnd('\') -ine $binDir.TrimEnd('\') }) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $neu, 'User')
    Ok "PATH-Eintrag entfernt: $binDir"
}

# --------------------------------------------------------------------------- #
# 3) Globale Ablage (nur mit -Alles)
# --------------------------------------------------------------------------- #
if ($Alles) {
    Say 'Entferne die globale Ablage ...'
    Info 'Darin liegen: Einstellungen, dein OpenRouter-Schluessel, die Projektliste,'
    Info 'die Flugrouten (Discord/SMTP) und die Eingabe-Historie.'
    foreach ($d in @($home_dir, $legacy_dir)) {
        if (-not (Test-Path $d)) { continue }
        if ($DryRun) { Info "[dry-run] wuerde loeschen: $d"; continue }
        $antwort = Read-Host "   Wirklich loeschen? $d  [ja/NEIN]"
        if ($antwort -eq 'ja') {
            Remove-Item -LiteralPath $d -Recurse -Force
            Ok "geloescht: $d"
        }
        else {
            Info "behalten: $d"
        }
    }
}
else {
    Say 'Globale Ablage bleibt erhalten'
    Info "$home_dir"
    Info 'Mit -Alles wird sie mitentfernt (Einstellungen, Schluessel, Projektliste).'
}

# --------------------------------------------------------------------------- #
# 4) Was bleibt — bewusst
# --------------------------------------------------------------------------- #
Say 'Deine Dokumente bleiben unangetastet'
if ($projekte.Count -gt 0) {
    Info 'PollySort kannte diese Projektordner:'
    foreach ($p in $projekte) { Info "  $p" }
    Info ''
    Info 'Dort liegen deine einsortierten Dateien und je ein verstecktes `.honig`.'
    Info 'Darin steckt auch `papierkorb` - die Quarantaene, die noch echte Dateien'
    Info 'enthalten kann. Deshalb ruehrt dieser Deinstaller sie nicht an. Wenn du'
    Info 'sicher bist, dass nichts mehr drin ist, kannst du die `.honig`-Ordner'
    Info 'selbst loeschen; die Kategorie-Ordner bleiben dann normale Ordner.'
}
else {
    Info 'Keine Projektordner bekannt.'
}

Say 'Fertig.'
if (-not $DryRun) { Info 'Neues Terminal oeffnen, damit der PATH neu gelesen wird.' }
