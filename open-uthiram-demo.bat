@echo off
setlocal
cd /d "%~dp0"

set "FRONTEND_DIR=%~dp0frontend"
set "APP_URL=http://127.0.0.1:5173/"

where.exe node >nul 2>&1
if errorlevel 1 (
  echo ERROR: Node.js is required. Install Node.js and retry.
  exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
  echo ERROR: The frontend package was not found at "%FRONTEND_DIR%".
  exit /b 1
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200 -and $r.Content -match 'Uthiram') { exit 0 }; exit 2 } catch { exit 1 }" >nul 2>&1
if errorlevel 2 (
  echo ERROR: Port 5173 is serving a different site. Stop that service and retry.
  exit /b 1
)
if not errorlevel 1 goto open_browser

if not exist "%FRONTEND_DIR%\node_modules\vite\bin\vite.js" (
  echo Installing frontend dependencies from package-lock.json...
  pushd "%FRONTEND_DIR%"
  call npm.cmd ci
  set "NPM_RESULT=%ERRORLEVEL%"
  popd
  if not "%NPM_RESULT%"=="0" (
    echo ERROR: Frontend dependency installation failed.
    exit /b 1
  )
)

 echo Starting Uthiram frontend...
powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm.cmd run dev -- --host 127.0.0.1 --strictPort' -WorkingDirectory '%FRONTEND_DIR%' -WindowStyle Minimized"
if errorlevel 1 (
  echo ERROR: Could not start the Vite development server.
  exit /b 1
)

set "APP_READY=0"
for /l %%I in (1,1,45) do (
  powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200 -and $r.Content -match 'Uthiram') { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 (
    set "APP_READY=1"
    goto server_ready
  )
  timeout /t 2 /nobreak >nul
)

:server_ready
if "%APP_READY%"=="0" (
  echo ERROR: Uthiram did not become ready within 90 seconds.
  echo Check Node.js, dependencies, and whether port 5173 is available.
  exit /b 1
)

:open_browser
set "CHROME="
if defined CHROME_PATH if exist "%CHROME_PATH%" set "CHROME=%CHROME_PATH%"
if not defined CHROME if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME (
  start "Uthiram" "%CHROME%" "%APP_URL%"
) else (
  echo Chrome was not found; opening your default browser.
  start "" "%APP_URL%"
)

exit /b 0
