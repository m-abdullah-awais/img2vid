@echo off
setlocal
cd /d "%~dp0"

rem The folders the instructions in this file point at. Setup.bat creates them
rem too, but they are gitignored and git cannot carry an empty folder, so a copy
rem that was cloned or unzipped and never set up has none of them. Making them
rem here as well means a user is never told to open a folder that is not there.
for %%D in ("input\audio" "input\images" "output") do if not exist "%%~D" mkdir "%%~D" 2>nul

rem ==========================================================================
rem  Optional helper.  Puts input\images in order and numbers them.
rem
rem  The video is built from the images in filename order, one per transcript
rem  line, so the names decide which image goes where. Camera and download
rem  names do not sort that way. This renames them
rem
rem    IMG_20260401_182233.jpg  ->  001.jpg
rem    screenshot (10).png      ->  002.png
rem
rem  oldest first, by the date each file was created. It shows the list and
rem  asks before changing anything, and the previous names can be put back.
rem
rem  Options. Put any flags you always want between the quotes below.
rem
rem    --dry-run      show what would be renamed and change nothing
rem    --by modified  order by date modified instead of date created
rem    --by name      order by the current filenames
rem    --start 0      number from 000 instead of 001
rem    --digits 1     name them 1, 2, 3 instead of 001, 002, 003
rem    --undo         put back the names from the previous run
rem
rem  Example:  set "FLAGS=--by modified"
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

%PY% rename_images.py %FLAGS% %*
set "CODE=%ERRORLEVEL%"

rem 2 means nothing was renamed, either because the folder is still empty or
rem because the question was answered with no. Neither is a failure.
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
