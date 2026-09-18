@echo off
setlocal
cd /d "%~dp0"

rem ==========================================================================
rem  Start img2vid. Double click this and it opens in your browser.
rem
rem  It starts the engine and the web app together in this one window, then
rem  opens the app. Everything else happens in the browser: uploading the
rem  narration and images, building the video and downloading it.
rem
rem  Keep this window open while you work. Close it, or press Ctrl+C, to stop
rem  img2vid, including any video still being built.
rem
rem  On a new machine, run Setup.bat once first.
rem
rem  Options:
rem    Run.bat --no-browser   start without opening a browser tab
rem    Run.bat --port 3100    serve the web app on another port
rem    Run.bat --dev          run the web app in development mode, for working
rem                           on the frontend
rem ==========================================================================

rem Pause at the end only when this file was double clicked and something went
rem wrong, so the message stays readable instead of the window vanishing.
set "HOLD="
echo %cmdcmdline% | find /i "%~nx0" >nul && set "HOLD=1"

rem A copy set up before the web app kept its private tools in runtime\ and bin\
rem at the top of the folder. Setup.bat moves them too; doing it here as well
rem means updating the files and double clicking this is enough.
if exist "runtime\" if not exist "backend\runtime\" move "runtime" "backend\runtime" >nul 2>&1
if exist "bin\ffmpeg.exe" if not exist "backend\runtime\bin\ffmpeg.exe" (
    if not exist "backend\runtime\bin" mkdir "backend\runtime\bin"
    move "bin\ffmpeg.exe" "backend\runtime\bin\ffmpeg.exe" >nul 2>&1
    if exist "bin\ffprobe.exe" move "bin\ffprobe.exe" "backend\runtime\bin\ffprobe.exe" >nul 2>&1
    rmdir "bin" 2>nul
)

rem Find a Python. The private copy that Setup.bat may have unpacked wins, so a
rem folder that was set up portably keeps working on a machine with no Python.
rem A Python on PATH only counts if it actually runs: a clean Windows keeps a
rem Microsoft Store stub called python.exe on the PATH that opens the Store.
set "PY="
if exist "backend\runtime\python\python.exe" set "PY=backend\runtime\python\python.exe"
for %%C in (python py) do (
    if not defined PY (
        %%C -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY=%%C"
    )
)
if not defined PY (
    echo.
    echo   ERROR: Python was not found.
    echo   Run Setup.bat first. It uses the system Python if there is one,
    echo   and otherwise unpacks a private copy into this folder.
    goto :finish
)

if not exist "backend\runtime\bin\ffmpeg.exe" (
    where ffmpeg >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ERROR: ffmpeg was not found.
        echo   Run Setup.bat first. It uses the system ffmpeg if there is one,
        echo   and otherwise unpacks a private copy into this folder.
        goto :finish
    )
)

rem Node.js serves the web app. Next.js needs version 20 or newer.
if exist "backend\runtime\node\node.exe" (
    set "PATH=%~dp0backend\runtime\node;%PATH%"
) else (
    node -e "process.exit(+process.versions.node.split('.')[0]>=20?0:1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ERROR: Node.js 20 or newer was not found.
        echo   Run Setup.bat first. It uses the system Node.js if there is one,
        echo   and otherwise unpacks a private copy into this folder.
        goto :finish
    )
)

rem npm's download cache and Next.js telemetry both default to the user
rem profile. Nothing this project does is allowed to land outside its folder.
set "npm_config_cache=%~dp0backend\runtime\npm-cache"
set "NEXT_TELEMETRY_DISABLED=1"

%PY% backend\cli\start.py %*
set "CODE=%ERRORLEVEL%"

:finish
if not defined CODE set "CODE=1"
if defined HOLD if not "%CODE%"=="0" (
    echo.
    pause
)
exit /b %CODE%
