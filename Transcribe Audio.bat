@echo off
setlocal
cd /d "%~dp0"

rem The folders the instructions in this file point at. Setup.bat creates them
rem too, but they are gitignored and git cannot carry an empty folder, so a copy
rem that was cloned or unzipped and never set up has none of them. Making them
rem here as well means a user is never told to open a folder that is not there.
for %%D in ("input\audio" "input\images" "output") do if not exist "%%~D" mkdir "%%~D" 2>nul

rem ==========================================================================
rem  Step 1 of 2.  Audio  ->  timestamped transcript.
rem
rem  Put your narration in input\audio\ and run this. It writes:
rem
rem    input\script.srt      the transcript Create Video.bat reads
rem    input\script.txt      the same thing, readable at a glance
rem
rem  One line of transcript becomes one image, so the number of lines it
rem  reports is the number of images you need.
rem
rem  Options. Put any flags you always want between the quotes below.
rem
rem    --max-chars 90     split long lines, so you get more, shorter images
rem    --min-seconds 2    merge very short lines
rem    --pick             choose one audio file instead of joining them all
rem    --language en      skip language detection, slightly faster
rem    --fresh            ignore the cached result and transcribe again
rem    --batch 8          about 25 percent faster, but measurably less accurate
rem    --model small      bigger model. Measured on this machine it was seven
rem                       times slower than the default and no more accurate,
rem                       so try it only if the default struggles with your audio
rem
rem  Example:  set "FLAGS=--max-chars 90"
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

rem The speech engine is a separate download, so say so plainly rather than
rem letting the import fail deeper in.
if not exist "runtime\whisper\lib" (
    echo.
    echo   ERROR: the speech engine is not installed.
    echo   Run Setup.bat. It installs it inside this folder, nothing system wide.
    goto :finish
)

%PY% transcribe.py %FLAGS% %*
set "CODE=%ERRORLEVEL%"

rem 2 means the input folder still needs filling in, which is not a failure.
if not "%CODE%"=="0" if not "%CODE%"=="2" (
    echo.
    echo   Finished with errors. See the message above.
)

:finish
if not defined CODE set "CODE=1"
if defined HOLD (
    echo.
    pause
)
exit /b %CODE%
