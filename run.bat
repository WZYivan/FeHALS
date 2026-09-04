@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ===========================================================================
rem  FeHALS Windows launcher
rem
rem  Usage: run.bat [start|stop|restart|status]   (default: start)
rem    start    Start backend (port 8000) and frontend (port 5173)
rem    stop     Stop both services (by port)
rem    restart  Stop then start
rem    status   Show running status
rem ===========================================================================

set "PROJ=%~dp0"

rem --- Configurable (override via environment variables) ---
if not defined BACKEND_PORT  set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"
rem CONDA_ENV 留空时后端用系统 Python 3.9（py -3.9）；如需 conda 环境，在此处填名字
if not defined CONDA_ENV     set "CONDA_ENV="

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=start"

if /I "%ACTION%"=="start"    goto :do_start
if /I "%ACTION%"=="stop"     goto :do_stop
if /I "%ACTION%"=="restart"  goto :do_restart
if /I "%ACTION%"=="status"   goto :do_status

echo Usage: run.bat [start^|stop^|restart^|status]
exit /b 1

rem ---------------------------------------------------------------------------
:do_start
call :port_listening %BACKEND_PORT%
if errorlevel 1 (
  echo [ERROR] Port %BACKEND_PORT% is in use, run "run.bat stop" first.
  exit /b 1
)
call :port_listening %FRONTEND_PORT%
if errorlevel 1 (
  echo [ERROR] Port %FRONTEND_PORT% is in use, run "run.bat stop" first.
  exit /b 1
)

call :check_env

echo [START] Backend  (port %BACKEND_PORT%)...
set "BACKEND_CMD=py -3.9 run.py"
if not "%CONDA_ENV%"=="" (
  where conda >nul 2>nul
  if not errorlevel 1 set "BACKEND_CMD=conda run -n %CONDA_ENV% python run.py"
)
start "FeHALS-Backend" /D "%PROJ%backend" cmd /k "!BACKEND_CMD!"

echo [START] Frontend (port %FRONTEND_PORT%)...
start "FeHALS-Frontend" /D "%PROJ%frontend" cmd /k "npx vite --port %FRONTEND_PORT%"

echo.
echo Backend : http://localhost:%BACKEND_PORT%  [docs at /docs]
echo Frontend: http://localhost:%FRONTEND_PORT%
echo Logs are shown in two separate windows; run "run.bat stop" to stop.
exit /b 0

rem ---------------------------------------------------------------------------
:do_stop
echo [STOP] Backend (port %BACKEND_PORT%)...
call :kill_port %BACKEND_PORT%
rem Also kill uvicorn reloader parent (python processes whose command line contains run.py)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'Name=''python.exe''' | Where-Object { $_.CommandLine -like '*run.py*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { taskkill /PID $_ /T /F 2>$null | Out-Null }"

echo [STOP] Frontend (port %FRONTEND_PORT%)...
call :kill_port %FRONTEND_PORT%
echo Services stopped.
exit /b 0

rem ---------------------------------------------------------------------------
:do_restart
call :do_stop
timeout /t 2 /nobreak >nul
call :do_start
exit /b 0

rem ---------------------------------------------------------------------------
:do_status
call :port_listening %BACKEND_PORT%
if errorlevel 1 (
  echo Backend : running  http://localhost:%BACKEND_PORT%
) else (
  echo Backend : stopped
)
call :port_listening %FRONTEND_PORT%
if errorlevel 1 (
  echo Frontend: running  http://localhost:%FRONTEND_PORT%
) else (
  echo Frontend: stopped
)
exit /b 0

rem ---------------------------------------------------------------------------
rem Environment check: conda / node / npm / HELIOS++ paths
:check_env
where py >nul 2>nul
if errorlevel 1 (
  echo [WARN] Python launcher "py" not found - set CONDA_ENV to a valid conda env,
  echo        or install deps into a Python 3.9:  pip install -r backend\requirements.txt
)
where node >nul 2>nul
if errorlevel 1 echo [WARN] node not found. Install Node.js.
where npm  >nul 2>nul
if errorlevel 1 echo [WARN] npm not found.

if defined HELIOS_PATH goto :show_helios
echo [HELIOS] HELIOS_PATH not set - simulation disabled; 3D preview still works.
echo         On Windows, set HELIOS_PATH / HELIOS_REPO / HELIOS_ASSETS after installing HELIOS++.
goto :after_helios
:show_helios
echo [HELIOS] HELIOS_PATH=%HELIOS_PATH%
:after_helios
exit /b 0

rem ---------------------------------------------------------------------------
rem Return 1 if the port is listening, otherwise 0
:port_listening
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
exit /b %errorlevel%

rem ---------------------------------------------------------------------------
rem Force-kill the process (and its tree) listening on the given port
:kill_port
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { taskkill /PID $_ /T /F 2>$null | Out-Null }"
exit /b 0