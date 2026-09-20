@echo off
setlocal
cd /d "%~dp0"

rem ==========================================================================
rem  Free up ports and disk space.
rem
rem  Opens a numbered menu. Nothing is removed until you choose an item and
rem  answer its question, and a bare Enter always means no.
rem
rem  Your projects are never touched: narration, transcripts, images and
rem  finished videos are your work and are left exactly as they are. What this
rem  clears is what the app made for itself and can make again:
rem
rem    - stops img2vid and frees the ports it was using
rem    - thumbnails, waveforms and the preview's audio
rem    - the transcription cache and the encoder choice
rem    - half finished uploads, renders and job folders
rem    - the trash, which normally empties itself after 7 days
rem    - the web app's build and its packages
rem    - scratch files in temp
rem ==========================================================================

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
    echo   Run Setup.bat first. It will use the system Python if there is one,
    echo   and otherwise unpack a private copy into this folder.
    goto :finish
)

%PY% backend\cli\cleanup.py %*
set "CODE=%ERRORLEVEL%"

:finish
if not defined CODE set "CODE=1"
rem Pause only when double clicked, so a terminal or a script is unaffected.
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b %CODE%
