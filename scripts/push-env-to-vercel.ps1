<#
Push every KEY=VALUE in backend/.env to the linked Vercel project as an
Environment Variable, across Production / Preview / Development.

Usage (from the repo root):
    # one-time setup
    npm install -g vercel
    vercel login
    vercel link   # pick ai-cyber-security-platform

    # then
    pwsh scripts/push-env-to-vercel.ps1
    # or if you're in plain PowerShell:
    powershell -ExecutionPolicy Bypass -File scripts/push-env-to-vercel.ps1

The script never echoes your values — they're piped straight to `vercel env add`.
Empty values (like PHISHTANK_API_KEY=) are skipped.
#>

param(
    [string]$EnvFile = "backend/.env"
)

if (-not (Test-Path $EnvFile)) {
    Write-Host "❌  Couldn't find $EnvFile" -ForegroundColor Red
    exit 1
}

# Make sure the vercel CLI is installed + project is linked.
$vercelCmd = Get-Command vercel -ErrorAction SilentlyContinue
if (-not $vercelCmd) {
    Write-Host "❌  Vercel CLI not found. Run: npm install -g vercel" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path ".vercel/project.json")) {
    Write-Host "❌  This folder isn't linked to a Vercel project. Run: vercel link" -ForegroundColor Red
    exit 1
}

$targets = @("production", "preview", "development")

Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }

    $eq = $line.IndexOf("=")
    if ($eq -lt 1) { return }

    $name  = $line.Substring(0, $eq).Trim()
    $value = $line.Substring($eq + 1).Trim()

    if (-not $value) {
        Write-Host "  skip $name (empty)" -ForegroundColor DarkYellow
        return
    }

    foreach ($env in $targets) {
        Write-Host "  push $name -> $env" -ForegroundColor Cyan
        # Silently remove an existing var first so re-runs don't blow up.
        vercel env rm $name $env --yes 2>$null | Out-Null
        # Pipe the value as stdin so it never appears in the process list.
        $value | vercel env add $name $env | Out-Null
    }
}

Write-Host ""
Write-Host "✅  Done. Now redeploy from the Vercel dashboard or run:" -ForegroundColor Green
Write-Host "       vercel --prod" -ForegroundColor Green
