<#
.SYNOPSIS
    Full restart & deploy: Docker services -> Vercel backend -> Streamlit Cloud.
    Run from the project root:  .\deploy.ps1

.DESCRIPTION
    1. Stops and removes existing Docker containers/images (clean slate).
    2. Rebuilds and starts Docker Compose (Postgres, Redis, FastAPI, Streamlit).
    3. Waits for the local API health check to pass.
    4. Deploys the Vercel backend (production).
    5. Pushes latest code to the Streamlit Cloud branch (triggers redeploy).

.NOTES
    Prerequisites:
      - Docker Desktop running
      - Vercel CLI installed  (npm i -g vercel)
      - Git configured with remote for Streamlit Cloud
      - .env file present in project root
#>

param(
    [switch]$SkipDocker,       # Skip Docker rebuild (just redeploy cloud)
    [switch]$SkipVercel,       # Skip Vercel deploy
    [switch]$SkipStreamlit,    # Skip Streamlit Cloud push
    [switch]$NoPrune,          # Keep old Docker images
    [string]$Branch = "main"   # Git branch for Streamlit Cloud
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Helpers ---------------------------------------------------------------
function Write-Step  { param($m) Write-Host "`n>> $m" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "   [OK] $m" -ForegroundColor Green }
function Write-Warn  { param($m) Write-Host "   [WARN] $m" -ForegroundColor Yellow }
function Write-Fail  { param($m) Write-Host "   [FAIL] $m" -ForegroundColor Red }

# -- Pre-flight checks ---------------------------------------------
Write-Step "Pre-flight checks"

if (-not (Test-Path ".env")) {
    Write-Fail ".env file not found. Copy .env.example to .env and fill in your keys."
    exit 1
}
Write-Ok ".env file found"

if (-not $SkipDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Fail "Docker not found in PATH. Install Docker Desktop first."
        exit 1
    }
    # Verify Docker daemon is running.
    # docker info writes warnings to stderr, so temporarily relax ErrorAction
    # to prevent $ErrorActionPreference="Stop" from terminating on them.
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $null = docker info 2>&1
    $dockerExit = $LASTEXITCODE
    $ErrorActionPreference = $prevPref
    if ($dockerExit -ne 0) {
        Write-Fail "Docker daemon is not running. Start Docker Desktop first."
        exit 1
    }
    Write-Ok "Docker daemon is running"
}

if (-not $SkipVercel) {
    if (-not (Get-Command vercel -ErrorAction SilentlyContinue)) {
        Write-Warn "Vercel CLI not found. Install with: npm i -g vercel   (skipping Vercel deploy)"
        $SkipVercel = $true
    } else {
        Write-Ok "Vercel CLI found"
    }
}

if (-not $SkipStreamlit) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Warn "Git not found. Skipping Streamlit Cloud push."
        $SkipStreamlit = $true
    } else {
        Write-Ok "Git found"
    }
}

# ==================================================================
# PHASE 1 - Docker (local stack: Postgres + Redis + FastAPI + Streamlit)
# ==================================================================
if (-not $SkipDocker) {
    # Docker commands often write warnings to stderr (e.g. iptables, buildkit).
    # Temporarily relax ErrorActionPreference so those don't terminate the script.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    Write-Step "Stopping existing Docker containers"
    docker compose down --remove-orphans 2>&1 | Out-Null
    Write-Ok "Containers stopped"

    if (-not $NoPrune) {
        Write-Step "Removing old project images"
        $images = docker images --filter "reference=multiagent-trading-system*" -q 2>&1
        if ($images) {
            docker rmi $images --force 2>&1 | Out-Null
            Write-Ok "Old images removed"
        } else {
            Write-Ok "No old images to remove"
        }
    }

    Write-Step "Building & starting Docker Compose (Postgres, Redis, API, Streamlit)"
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $prevEAP
        Write-Fail "Docker Compose up failed (exit code $LASTEXITCODE)"
        exit 1
    }
    Write-Ok "Docker Compose started"

    $ErrorActionPreference = $prevEAP

    # Wait for API to become healthy
    Write-Step "Waiting for API health check (http://localhost:8000/api/v1/health)"
    $maxWait = 90          # seconds
    $elapsed = 0
    $healthy = $false

    while ($elapsed -lt $maxWait) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.status -eq "ok") {
                $healthy = $true
                break
            }
        } catch {
            # API not ready yet
        }
        Start-Sleep -Seconds 3
        $elapsed += 3
        Write-Host "   ... waiting ($elapsed s)" -ForegroundColor DarkGray
    }

    if ($healthy) {
        Write-Ok "API is healthy (took ~${elapsed}s)"
    } else {
        Write-Fail "API did not become healthy within ${maxWait}s. Check: docker compose logs api"
        exit 1
    }

    # Quick check Streamlit
    Write-Step "Checking Streamlit UI (http://localhost:8501)"
    Start-Sleep -Seconds 3
    try {
        $streamlitCheck = Invoke-WebRequest -Uri "http://localhost:8501" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($streamlitCheck.StatusCode -eq 200) {
            Write-Ok "Streamlit UI is running"
        }
    } catch {
        Write-Warn "Streamlit UI not responding yet - may still be starting. Check: docker compose logs streamlit"
    }
} else {
    Write-Warn "Docker phase skipped (--SkipDocker)"
}

# ==================================================================
# PHASE 2 - Vercel (serverless FastAPI backend)
# ==================================================================
if (-not $SkipVercel) {
    Write-Step "Deploying to Vercel (production)"
    npx vercel --prod --yes
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Vercel deploy failed (exit code $LASTEXITCODE)"
        exit 1
    }
    Write-Ok "Vercel production deploy complete"
} else {
    Write-Warn "Vercel deploy skipped (--SkipVercel)"
}

# ==================================================================
# PHASE 3 - Streamlit Cloud (push to trigger redeploy)
# ==================================================================
if (-not $SkipStreamlit) {
    Write-Step "Pushing to '$Branch' branch for Streamlit Cloud deploy"

    $status = git status --porcelain 2>&1
    if ($status) {
        Write-Warn "Working tree has uncommitted changes - committing them now"
        git add -A
        git commit -m "deploy: auto-commit before Streamlit Cloud push $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    }

    git push origin $Branch 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Git push to '$Branch' failed. Check your remote config."
        exit 1
    }
    Write-Ok "Pushed to '$Branch' - Streamlit Cloud will redeploy automatically"
} else {
    Write-Warn "Streamlit Cloud push skipped (--SkipStreamlit)"
}

# ==================================================================
# Summary
# ==================================================================
Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

if (-not $SkipDocker) {
    Write-Host "  Local:" -ForegroundColor White
    Write-Host "    API       : http://localhost:8000/docs" -ForegroundColor Gray
    Write-Host "    Streamlit : http://localhost:8501" -ForegroundColor Gray
    Write-Host "    Postgres  : localhost:5432" -ForegroundColor Gray
    Write-Host "    Redis     : localhost:6379" -ForegroundColor Gray
    Write-Host ""
}
if (-not $SkipVercel) {
    Write-Host "  Vercel      : https://vercel.com/dashboard" -ForegroundColor Gray
}
if (-not $SkipStreamlit) {
    Write-Host "  Streamlit   : https://share.streamlit.io" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Logs:  docker compose logs -f api       (FastAPI)" -ForegroundColor DarkGray
Write-Host "         docker compose logs -f streamlit  (Streamlit)" -ForegroundColor DarkGray
Write-Host ""
