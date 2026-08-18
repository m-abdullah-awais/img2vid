@echo off
setlocal
cd /d "%~dp0"

rem ==========================================================================
rem  Options. Put any flags you always want between the quotes below.
rem
rem    --force        build the video even when the number of images does not
rem                   match the number of transcript lines
rem    --fps 15       lower frame rate, renders faster, fine for a slideshow
rem    --fit cover    fill the frame and crop, instead of letterboxing
rem
rem  Example:  set "FLAGS=--force --fps 15"
rem
rem  You can also leave this empty and answer the prompt when it appears.
rem ==========================================================================
set "FLAGS="

rem Pause at the end only when this file was double clicked, so that running it
rem from a terminal or another script does not block waiting for a key.
set "HOLD="
echo %cmdcmdline% | find /i "%~nx0" >nul && set "HOLD=1"

rem Find a Python. The private copy that Setup.bat may have unpacked wins, so a
rem folder that was set up portably keeps working on a machine with no Python.
set "PY="
if exist "runtime\python\python.exe" set "PY=runtime\python\python.exe"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py"
if not defined PY (
    echo.
    echo   ERROR: Python was not found.
    echo   Run Setup.bat first. It will use the system Python if there is one,
    echo   and otherwise unpack a private copy into this folder.
    goto :finish
)

rem ffmpeg must be on PATH, or sitting in the project bin folder.
if not exist "bin\ffmpeg.exe" (
    where ffmpeg >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ERROR: ffmpeg was not found.
        echo   Run Setup.bat first. It will use the system ffmpeg if there is one,
        echo   and otherwise unpack a private copy into this folder.
        goto :finish
    )
)

%PY% run.py %FLAGS% %*
set "CODE=%ERRORLEVEL%"

rem 2 means the input folder still needs filling in, which is not a failure.
if not "%CODE%"=="0" if not "%CODE%"=="2" (
    echo.
    echo   Finished with errors. See the message above.
)

:finish
if defined HOLD (
    echo.
    pause
)
exit /b %CODE%
