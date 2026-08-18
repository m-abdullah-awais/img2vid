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

rem Find a Python launcher. "python" first, then the "py" launcher.
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py"
if not defined PY (
    echo.
    echo   ERROR: Python was not found.
    echo   Install Python 3.8 or newer and tick "Add Python to PATH", then run this again.
    echo   Download: https://www.python.org/downloads/
    goto :finish
)

rem ffmpeg must be on PATH, or sitting in the project bin folder.
if not exist "bin\ffmpeg.exe" (
    where ffmpeg >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   ERROR: ffmpeg was not found.
        echo   Either add ffmpeg to PATH, or copy ffmpeg.exe and ffprobe.exe
        echo   into this folder: "%~dp0bin"
        echo   Download: https://www.gyan.dev/ffmpeg/builds/
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
