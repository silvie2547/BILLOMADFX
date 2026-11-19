# BILLOMADFX: demo-only Algo Trading permissions helper.
# Never sends an MT5 order, never reads passwords, does not modify broker account credentials.
param(
    [string]$Mt5Path = 'C:\Program Files\MetaTrader 5\terminal64.exe'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$probePath = Join-Path $PSScriptRoot 'check_mt5_trade_permissions.py'

function Stop-WithMessage([string]$message) {
    Write-Host "`nSTOP: $message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $Mt5Path)) {
    Stop-WithMessage "MT5 not found at $Mt5Path. Run this script with -Mt5Path '<exact path to terminal64.exe>'."
}
if (-not (Test-Path -LiteralPath $probePath)) { Stop-WithMessage "Missing check_mt5_trade_permissions.py" }

$pyCmd = Get-Command py -ErrorAction SilentlyContinue
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pyCmd) {
    $pythonExe = $pyCmd.Source
    $pythonArgs = @('-3')
} elseif ($pythonCmd) {
    $pythonExe = $pythonCmd.Source
    $pythonArgs = @()
} else {
    Stop-WithMessage 'Python was not found. Install Python, then run this helper again.'
}

function Check-MT5 {
    $output = & $pythonExe @pythonArgs $probePath $Mt5Path 2>&1
    $exitCode = $LASTEXITCODE
    $raw = $output | Out-String
    try { $s = $raw | ConvertFrom-Json } catch { Stop-WithMessage "MT5 probe returned unexpected text: $raw" }
    if ($exitCode -ne 0 -or $s.error) { Stop-WithMessage "MT5 diagnostic: $($s.error)" }
    return $s
}

function Require-Demo($s) {
    Write-Host "Broker server: $($s.server) | Account ending: $($s.login_last4) | Type: $($s.account_type)" -ForegroundColor Cyan
    if ($s.account_type -ne 'DEMO') { Stop-WithMessage 'Account is not DEMO. No permissions were changed.' }
    if (-not $s.connected) { Stop-WithMessage 'Terminal is disconnected. Log into your Valetax demo account first.' }
    if (-not $s.account_trade_allowed) { Stop-WithMessage 'Broker/account has trading disabled. Check MT5 account permissions.' }
    if (-not $s.account_trade_expert) { Stop-WithMessage 'Broker/account does not permit expert/automated trading.' }
}

function Get-MT5Process {
    # If multiple terminals exist, fail closed rather than guessing which to activate.
    $candidates = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {
        try { [string]::Equals($_.Path, $Mt5Path, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
    if ($candidates.Count -ne 1) { return $null }
    if ($candidates[0].MainWindowHandle -eq [IntPtr]::Zero) { return $null }
    return $candidates[0]
}

Write-Host '================================================' -ForegroundColor Yellow
Write-Host ' BILLOMADFX | MT5 DEMO permissions helper' -ForegroundColor Yellow
Write-Host ' No BUY, SELL, or real-account orders are sent.'
Write-Host '================================================'
Write-Host 'Checking connected account and permissions...'
$s = Check-MT5
Require-Demo $s
Write-Host "Auto/Algo Trading allowed: $($s.trade_allowed)"
Write-Host "External Python API blocked: $($s.tradeapi_disabled)"

if (-not $s.trade_allowed) {
    Write-Host "`nAlgo Trading is currently OFF." -ForegroundColor Yellow
    $confirm = Read-Host "Type ENABLE DEMO to switch it ON for this demo account (or press Enter to cancel)"
    if ($confirm -cne 'ENABLE DEMO') { Stop-WithMessage 'No changes were made.' }
    $mt5proc = Get-MT5Process
    if ($null -eq $mt5proc) { Stop-WithMessage 'Could not uniquely identify the MT5 desktop window. Open MT5 and press Ctrl+E manually, then rerun.' }
    Add-Type -AssemblyName Microsoft.VisualBasic
    Add-Type -AssemblyName System.Windows.Forms
    try { [Microsoft.VisualBasic.Interaction]::AppActivate([int]$mt5proc.Id) }
    catch { Stop-WithMessage 'Cannot focus MT5. Open it and press Ctrl+E manually.' }
    Start-Sleep -Milliseconds 600
    [System.Windows.Forms.SendKeys]::SendWait('^e')  # Official MT5 Ctrl+E hotkey
    Start-Sleep -Seconds 2
    $s = Check-MT5
    Require-Demo $s
    if (-not $s.trade_allowed) {
        Stop-WithMessage 'Algo Trading is still OFF. In MT5 press Ctrl+E, then rerun this helper.'
    }
    Write-Host 'Algo Trading is now ON (confirmed by the MT5 API).' -ForegroundColor Green
}

if ($s.tradeapi_disabled) {
    Write-Host "`nMT5 is still blocking external Python orders." -ForegroundColor Yellow
    Write-Host 'This security setting has no supported Python setter.'
    Write-Host 'In MT5 open Tools > Options > Expert Advisors (Ctrl+O).'
    Write-Host 'UN-TICK: Disable automated trading via external Python API.'
    Write-Host 'Keep any protections related to switching accounts enabled.'
    Write-Host 'Click OK, then return here.'
    $null = Read-Host 'After making that deliberate change, press Enter to recheck'
    $s = Check-MT5
    Require-Demo $s
    if ($s.tradeapi_disabled) { Stop-WithMessage 'External Python API is still blocked. Recheck the Expert Advisors tab.' }
}

if ($s.trade_allowed -and -not $s.tradeapi_disabled -and $s.connected -and $s.account_type -eq 'DEMO') {
    Write-Host "`nMT5 DEMO PYTHON TRADING PERMISSIONS READY" -ForegroundColor Green
    Write-Host 'This confirms permissions only. NO order was submitted.'
    Write-Host 'Keep BILLOMADFX AUTO OFF for the next supervised demo-order test.'
} else {
    Stop-WithMessage 'A required permission is missing.'
}
