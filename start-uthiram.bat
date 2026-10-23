@echo off
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:5173/"
set "API_HEALTH_URL=http://127.0.0.1:8000/health"

echo Uthiram local development launcher
echo.

if not exist ".env" (
  echo ERROR: .env was not found.
  echo Copy .env.example to .env, review its development-only values, and retry.
  exit /b 1
)

for %%V in (DATABASE_URL JWT_SECRET TOTP_ENCRYPTION_KEY) do (
  findstr /r /b /c:"%%V=..*" .env >nul
  if errorlevel 1 (
    echo ERROR: .env must define %%V.
    exit /b 1
  )
)

findstr /i /c:"CHANGE_ME" .env >nul
if not errorlevel 1 (
  echo ERROR: Replace all CHANGE_ME placeholders in .env before starting Uthiram.
  exit /b 1
)

where.exe docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker was not found. Install and start Docker Desktop, then retry.
  exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Compose is unavailable. Update or start Docker Desktop.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Engine is not ready. Start Docker Desktop and retry.
  exit /b 1
)

docker compose config --quiet
if errorlevel 1 (
  echo ERROR: Docker Compose configuration is invalid. Check .env and docker-compose.yml.
  exit /b 1
)

echo This starts the local PostgreSQL service and applies the existing Alembic
echo migrations. Existing Docker volumes are preserved; no database volume is removed.
choice /c YN /m "Continue"
if errorlevel 2 exit /b 0

echo.
echo Starting PostgreSQL...
docker compose up -d db
if errorlevel 1 goto startup_error

echo Building API and frontend images...
docker compose build backend frontend
if errorlevel 1 goto startup_error

set "DB_READY=0"
for /l %%I in (1,1,60) do (
  docker compose exec -T db pg_isready >nul 2>&1
  if not errorlevel 1 (
    set "DB_READY=1"
    goto database_ready
  )
  timeout /t 2 /nobreak >nul
)

:database_ready
if "%DB_READY%"=="0" (
  echo ERROR: PostgreSQL did not become ready within 120 seconds.
  goto startup_error
)

echo Applying database migrations...
docker compose run --rm backend alembic upgrade head
if errorlevel 1 (
  echo ERROR: Database migration failed. Existing database data was not removed.
  goto startup_error
)

echo Starting API and frontend...
docker compose up -d backend frontend
if errorlevel 1 goto startup_error

set "APP_READY=0"
for /l %%I in (1,1,60) do (
  powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 3; if ($r.StatusCode -eq 200 -and $r.Content -match 'Uthiram') { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 (
    set "APP_READY=1"
    goto frontend_ready
  )
  timeout /t 2 /nobreak >nul
)

:frontend_ready
if "%APP_READY%"=="0" (
  echo ERROR: The frontend did not become ready within 120 seconds.
  goto startup_error
)

powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri '%API_HEALTH_URL%' -TimeoutSec 3; if ($r.status -eq 'ok') { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo ERROR: The FastAPI health check failed at %API_HEALTH_URL%.
  goto startup_error
)

set "CHROME="
if defined CHROME_PATH if exist "%CHROME_PATH%" set "CHROME=%CHROME_PATH%"
if not defined CHROME if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME (
  start "Uthiram" "%CHROME%" "%APP_URL%"
) else (
  echo Chrome was not found at the standard locations; opening the default browser.
  start "" "%APP_URL%"
)

echo Uthiram is ready at %APP_URL%
echo Services run in the background until stopped.
echo Use stop-uthiram.bat to stop containers without deleting database data.
exit /b 0

:startup_error
echo.
echo Startup did not complete. Review Docker Desktop and .env configuration.
echo Services already started remain available; stop them with stop-uthiram.bat.
exit /b 1