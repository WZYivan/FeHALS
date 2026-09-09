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
rem HELIOS++ conda 环境根目录，用于自动检测 helios++.exe 并设置环境变量。
rem 若已通过系统环境变量设置 HELIOS_PATH，则不覆盖；此处仅用于自动检测。
rem 也可通过 set HELIOS_PREFIX=你的conda环境路径 来覆盖默认检测路径。
if not defined HELIOS_PREFIX  set "HELIOS_PREFIX=%USERPROFILE%\helios"
rem Windows 上关闭 uvicorn reload 模式：reloader 子进程会与 asyncio 子进程
rem 创建冲突，导致 helios++ 仿真进程挂起、进度永远 0%。Linux 默认开启。
if not defined FEHALS_RELOAD  set "FEHALS_RELOAD=false"

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

rem 设置 HELIOS++ Windows 环境变量（覆盖 config.py 中的 Linux 默认路径）
call :setup_helios_env

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
rem HELIOS++ 环境变量自动检测与设置（Windows）
rem
rem 若 HELIOS_PATH 已通过系统环境变量设置，则不覆盖，直接返回。
rem 否则从 HELIOS_PREFIX（默认 %USERPROFILE%\helios）下的 conda 环境中
rem 自动检测 helios++.exe，设置 HELIOS_PATH、HELIOS_ASSETS，并将 conda
rem 的 bin 目录加入 PATH 以供 helios++.exe 加载运行时 DLL。
rem
rem config.py 中的默认路径保持为 Linux 路径，此处仅通过环境变量覆盖。
:setup_helios_env
if defined HELIOS_PATH exit /b 0
if not exist "%HELIOS_PREFIX%\Lib\site-packages\pyhelios\bin\helios++.exe" (
  echo [HELIOS] 未在 %HELIOS_PREFIX% 找到 helios++.exe，仿真功能不可用
  echo          可通过 set HELIOS_PREFIX=你的conda环境路径 来指定位置
  exit /b 0
)
set "HELIOS_PATH=%HELIOS_PREFIX%\Lib\site-packages\pyhelios\bin\helios++.exe"
set "HELIOS_ASSETS=%HELIOS_PREFIX%\Lib\site-packages\pyhelios"
rem helios++.exe 运行所需 DLL 路径（conda 环境的 bin 目录）
set "PATH=%HELIOS_PREFIX%;%HELIOS_PREFIX%\Library\mingw-w64\bin;%HELIOS_PREFIX%\Library\usr\bin;%HELIOS_PREFIX%\Library\bin;%HELIOS_PREFIX%\Scripts;%HELIOS_PREFIX%\bin;%PATH%"
echo [HELIOS] HELIOS_PATH=%HELIOS_PATH%
echo [HELIOS] HELIOS_ASSETS=%HELIOS_ASSETS%
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
