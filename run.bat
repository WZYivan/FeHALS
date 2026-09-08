@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ===========================================================================
rem  FeHALS Windows launcher
rem
rem  Usage: run.bat [start|stop|restart|status]   (default: start)
rem    start    Start backend (port 8000) and frontend (port 5173)
rem    stop     Stop both services
rem    restart  Stop then start
rem    status   Show running status
rem
rem  Overridable env vars:
rem    CONDA_ENV       conda env for backend (default: FeHALS)
rem    BACKEND_PORT    default 8000 (also applied to backend via FEHALS_PORT)
rem    FRONTEND_PORT   default 5173
rem    HELIOS_CONDA    Windows HELIOS++ conda env root (default: C:\Users\31130\helios)
rem    HELIOS_PATH     default: <HELIOS_CONDA>\Lib\site-packages\pyhelios\bin\helios++.exe
rem    HELIOS_REPO     default: <HELIOS_CONDA>\Lib\site-packages\pyhelios
rem    HELIOS_ASSETS   default: <HELIOS_REPO>
rem ===========================================================================

set "PROJ=%~dp0"

if not defined BACKEND_PORT  set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"
if not defined CONDA_ENV     set "CONDA_ENV=FeHALS"

rem ---------------------------------------------------------------------------
rem  Windows 环境变量覆盖：config.py 以 Linux 为默认基准（参考 config1.py），
rem  本文件在此通过环境变量覆盖为 Windows 本机路径，无需修改 config.py。
rem ---------------------------------------------------------------------------

rem 让后端实际监听端口跟随 BACKEND_PORT（config.py 读取 FEHALS_PORT）
if not defined FEHALS_PORT  set "FEHALS_PORT=%BACKEND_PORT%"

rem HELIOS++ Windows Conda 安装路径（已设置时保留用户值）
if not defined HELIOS_CONDA  set "HELIOS_CONDA=C:\Users\31130\helios"
if not defined HELIOS_PATH   set "HELIOS_PATH=%HELIOS_CONDA%\Lib\site-packages\pyhelios\bin\helios++.exe"
if not defined HELIOS_REPO   set "HELIOS_REPO=%HELIOS_CONDA%\Lib\site-packages\pyhelios"
if not defined HELIOS_ASSETS set "HELIOS_ASSETS=%HELIOS_REPO%"

rem 将 HELIOS++ Conda 环境的 DLL 目录加入 PATH（Windows 运行 helios++.exe 必需）
if defined HELIOS_CONDA if exist "%HELIOS_CONDA%\Library\bin" (
  set "PATH=%HELIOS_CONDA%;%HELIOS_CONDA%\Library\bin;%HELIOS_CONDA%\Library\usr\bin;%HELIOS_CONDA%\Scripts;%PATH%"
)

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
call :check_env

call :port_listening %BACKEND_PORT%
if errorlevel 1 (
  echo [WARN] Port %BACKEND_PORT% in use - killing it first...
  call :kill_port %BACKEND_PORT%
  timeout /t 1 /nobreak >nul
)
call :port_listening %FRONTEND_PORT%
if errorlevel 1 (
  echo [WARN] Port %FRONTEND_PORT% in use - killing it first...
  call :kill_port %FRONTEND_PORT%
  timeout /t 1 /nobreak >nul
)

rem ---- Backend（解释器选择：优先 conda 环境，其次 Python314，最后 PATH python）----
set "BACKEND_CMD=python run.py"
where conda >nul 2>nul
if not errorlevel 1 (
  call :conda_env_exists %CONDA_ENV%
  if not errorlevel 1 set "BACKEND_CMD=conda run -n %CONDA_ENV% python run.py"
)
if "%BACKEND_CMD%"=="python run.py" if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
  set "BACKEND_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe" run.py"
)

echo [START] Backend on port %BACKEND_PORT% ...
start "FeHALS-Backend" /D "%PROJ%backend" cmd /k "%BACKEND_CMD%"

rem ---- Frontend ----
echo [START] Frontend on port %FRONTEND_PORT% ...
start "FeHALS-Frontend" /D "%PROJ%frontend" cmd /k "npx vite --port %FRONTEND_PORT%"

echo.
echo Backend : http://localhost:%BACKEND_PORT%   [API docs at /docs]
echo Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo Keep both windows open. Stop with: run.bat stop
exit /b 0

rem ---------------------------------------------------------------------------
:do_stop
echo [STOP] Backend on port %BACKEND_PORT% ...
call :kill_port %BACKEND_PORT%
rem Also kill python processes whose command line contains run.py (uvicorn)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*run.py*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { taskkill /PID $_ /T /F 2>$null | Out-Null }"

echo [STOP] Frontend on port %FRONTEND_PORT% ...
call :kill_port %FRONTEND_PORT%
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -like '*vite*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { taskkill /PID $_ /T /F 2>$null | Out-Null }"

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
set "BACKEND_STATE=stopped"
call :port_listening %BACKEND_PORT%
if errorlevel 1 set "BACKEND_STATE=running"
set "FRONTEND_STATE=stopped"
call :port_listening %FRONTEND_PORT%
if errorlevel 1 set "FRONTEND_STATE=running"

echo Backend : %BACKEND_STATE%  http://localhost:%BACKEND_PORT%
echo Frontend: %FRONTEND_STATE% http://localhost:%FRONTEND_PORT%
exit /b 0

rem ---------------------------------------------------------------------------
:check_env
where node >nul 2>nul
if errorlevel 1 echo [WARN] node not found. Please install Node.js.

where conda >nul 2>nul
if errorlevel 1 (
  echo [WARN] conda not found; will use plain "python run.py".
  where python >nul 2>nul
  if errorlevel 1 echo [ERROR] python not found.
) else (
  call :conda_env_exists %CONDA_ENV%
  if errorlevel 1 (
    echo [WARN] conda env "%CONDA_ENV%" not found - will use installed Python.
  ) else (
    echo [INFO] Backend will run in conda env: %CONDA_ENV%
  )
)

if defined HELIOS_PATH (
  if exist "%HELIOS_PATH%" (
    echo [HELIOS] HELIOS_PATH=%HELIOS_PATH%
  ) else (
    echo [WARN] HELIOS_PATH points to a missing file: %HELIOS_PATH%
    echo        Check HELIOS_CONDA / HELIOS_PATH overrides in run.bat, or run setup_helios_env.bat.
  )
) else (
  echo [HELIOS] HELIOS_PATH not set - simulation will fail at runtime.
  echo           Run "setup_helios_env.bat" in this console first, or set
  echo           HELIOS_PATH / HELIOS_REPO manually.
)
exit /b 0

rem ---------------------------------------------------------------------------
rem Return 0 if conda env with the given name exists, otherwise 1
:conda_env_exists
conda env list 2>nul | findstr /b /c:"%1 " >nul 2>nul
exit /b %errorlevel%

rem ---------------------------------------------------------------------------
rem Return errorlevel 1 if the port is listening, otherwise 0
:port_listening
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
exit /b %errorlevel%

rem ---------------------------------------------------------------------------
rem Force-kill the process tree listening on the given port
:kill_port
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { taskkill /PID $_ /T /F 2>$null | Out-Null }"
exit /b 0
