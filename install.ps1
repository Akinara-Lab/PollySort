# ---------------------------------------------------------------------------
# PollySort — Installer für Windows (PowerShell)
#
# Installiert das Tool isoliert (uv -> pipx -> pip --user) und trägt den Ordner mit
# den Programmen dauerhaft in den Benutzer-PATH ein, damit `pollysort` überall läuft.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   .\install.ps1 -NoPath      installieren, PATH nicht anfassen
#   .\install.ps1 -DryRun      nur zeigen, was passieren würde
#
# Der PATH wird ausschließlich im BENUTZER-Bereich geändert (HKCU) — nie systemweit,
# und Administratorrechte sind nicht nötig.
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [switch]$NoPath,
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

Set-Location -LiteralPath $PSScriptRoot
Say 'PollySort-Installer'
if ($DryRun) { Warn 'Trockenlauf - es wird nichts veraendert.' }

# --------------------------------------------------------------------------- #
# 1) Voraussetzungen
# --------------------------------------------------------------------------- #
if (-not (Test-Path 'pyproject.toml')) {
    Fail 'pyproject.toml nicht gefunden - bitte install.ps1 im PollySort-Ordner ausfuehren.'
    exit 1
}
Ok 'Projektdateien gefunden'

# Den ersten Kandidaten nehmen, der WIRKLICH ein passendes Python ist.
# Wichtig: 'python'/'python3' sind unter Windows oft nur Microsoft-Store-Platzhalter,
# die beim Aufruf lediglich eine Werbemeldung ausgeben - die duerfen wir nicht waehlen.
$py = $null
$pyAny = $null
$pyAnyVer = $null
foreach ($c in @('py', 'python', 'python3')) {
    if (-not (Has-Command $c)) { continue }
    # Ohne innere Anfuehrungszeichen und ohne '%': PowerShell reicht native Argumente
    # sonst verstuemmelt an das Programm weiter.
    # Ohne innere Anfuehrungszeichen und ohne '%': PowerShell reicht native Argumente
    # sonst verstuemmelt an das Programm weiter.
    $probe = Invoke-Tool $c @('-c', 'import platform; print(platform.python_version())')
    $ver = $probe.Ausgabe.Trim()
    if ($probe.Code -ne 0 -or $ver -notmatch '^\d+\.\d+') { continue }   # Platzhalter
    $pyAny = $c; $pyAnyVer = $ver
    $passt = Invoke-Tool $c @('-c', 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)')
    if ($passt.Code -eq 0) { $py = $c; break }
}
if (-not $py -and $pyAny) {
    Fail "Python 3.12+ benoetigt - gefunden wurde nur $pyAny ($pyAnyVer)."
    Info 'Aktuelle Version: https://www.python.org/downloads/'
    exit 1
}
if (-not $py) {
    Fail 'Kein funktionierendes Python gefunden.'
    Info 'Bitte Python 3.12+ installieren: https://www.python.org/downloads/'
    Info "Hinweis: 'python3' ist unter Windows oft nur ein Store-Platzhalter ohne Funktion."
    exit 1
}
Ok "Python $pyAnyVer gefunden ($py)"

# --------------------------------------------------------------------------- #
# 2) Installieren
# --------------------------------------------------------------------------- #
Say 'Installiere PollySort (mit Text-Extraktion [extract]) ...'
$binDir = $null

if (Has-Command 'uv') {
    Ok 'uv erkannt'
    if (-not $DryRun) { Invoke-Tool 'uv' @('tool', 'install', '--force', '.[extract]') | Out-Null }
    $binDir = Join-Path $env:USERPROFILE '.local\bin'
}
elseif (Has-Command 'pipx') {
    Ok 'pipx erkannt'
    if (-not $DryRun) { Invoke-Tool 'pipx' @('install', '--force', '.[extract]') | Out-Null }
    $binDir = (Invoke-Tool 'pipx' @('environment', '--value', 'PIPX_BIN_DIR')).Ausgabe.Trim()
    if (-not $binDir) { $binDir = Join-Path $env:USERPROFILE '.local\bin' }
}
else {
    Ok 'Weder uv noch pipx - verwende pip (Benutzer-Installation)'
    if (-not $DryRun) { Invoke-Tool $py @('-m', 'pip', 'install', '--user', '.[extract]') | Out-Null }
    $userBase = (Invoke-Tool $py @('-c', 'import site; print(site.getuserbase())')).Ausgabe.Trim()
    $binDir = Join-Path $userBase 'Scripts'
}
Info "Programme landen in: $binDir"

# --------------------------------------------------------------------------- #
# 3) PATH - dauerhaft im Benutzer-Bereich
# --------------------------------------------------------------------------- #
function Add-ToUserPath($dir) {
    # Der gespeicherte Benutzer-PATH, NICHT $env:Path (der enthaelt auch den System-Teil;
    # ihn zurueckzuschreiben wuerde Systemeintraege in den Benutzer-PATH kopieren).
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($null -eq $current) { $current = '' }

    $parts = $current -split ';' | Where-Object { $_ -ne '' }
    $already = $parts | Where-Object { $_.TrimEnd('\') -ieq $dir.TrimEnd('\') }
    if ($already) {
        Ok "PATH-Eintrag steht schon im Benutzer-PATH"
        return
    }
    if ($DryRun) {
        Info "[dry-run] wuerde '$dir' an den Benutzer-PATH anhaengen"
        return
    }
    $new = (@($parts) + $dir) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $new, 'User')
    Ok "PATH dauerhaft ergaenzt (Benutzer): $dir"
    Info 'Wirksam in neuen Terminals - dieses Fenster wurde bereits mitversorgt.'
}

if ($NoPath) {
    Warn '-NoPath gesetzt - PATH bleibt unangetastet.'
}
else {
    # Die Werkzeuge bringen eigene Mechanismen mit - die zuerst.
    if (Has-Command 'uv')   { if (-not $DryRun) { Invoke-Tool 'uv' @('tool', 'update-shell') | Out-Null } }
    if (Has-Command 'pipx') { if (-not $DryRun) { Invoke-Tool 'pipx' @('ensurepath') | Out-Null } }
    Add-ToUserPath $binDir
}

# Fuer die laufende Sitzung sofort verfuegbar machen.
if ($binDir -and ($env:Path -notlike "*$binDir*")) { $env:Path = "$binDir;$env:Path" }

# --------------------------------------------------------------------------- #
# 4) Ergebnis
# --------------------------------------------------------------------------- #
Say 'Pruefe Installation ...'
if ($DryRun) {
    Info 'Trockenlauf beendet - nichts wurde veraendert.'
    exit 0
}
if (Has-Command 'pollysort') {
    $ver = (Invoke-Tool 'pollysort-cli' @('--version')).Ausgabe.Trim()
    if (-not $ver) { $ver = 'bereit' }
    Ok "Befehl 'pollysort' verfuegbar ($ver)"
    Say 'Fertig! Tippe einfach:  pollysort'
    exit 0
}
else {
    Fail "'pollysort' ist in dieser Sitzung noch nicht auffindbar."
    Info 'Oeffne ein neues Terminal - der PATH-Eintrag greift dort.'
    Info "Notfalls direkt aus dem Repo starten:  $py polly.py"
    exit 1
}
