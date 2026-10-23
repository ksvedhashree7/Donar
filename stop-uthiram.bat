@echo off
setlocal
cd /d "%~dp0"

where.exe docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker was not found.
  exit /b 1
)

docker compose stop frontend backend db minio
if errorlevel 1 (
  echo ERROR: One or more Uthiram services could not be stopped.
  exit /b 1
)

echo Uthiram services stopped. PostgreSQL data volumes were preserved.