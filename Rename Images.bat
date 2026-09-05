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
rem    --insert FILE --at 5   put an image in at number 5, then renumber.
rem                   Repeat the pair to insert more than one.
rem    --dry-run      show what would be renamed and change nothing
rem    --by created   date created, oldest first. The default, except on a
rem                   folder whose names are already numbered, where that
rem                   numbering is kept unless you ask for this
rem    --by modified  date modified, oldest first
rem    --by name      filename, A to Z
rem    --by size      file size, smallest first
rem    --by type      file type, then filename
rem    --by random    shuffle. --seed 7 repeats the same shuffle
rem    --desc         reverse whichever order you picked
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

rem --------------------------------------------------------------------------
rem  Ask before doing anything, so opening this by mistake costs nothing.
rem  This one renames your files, so it matters most here. There is a second
rem  question later, after the exact list of renames has been printed, so
rem  nothing moves until you have seen exactly what will move.
rem --------------------------------------------------------------------------
if not defined HOLD goto :confirmed
echo.
echo   Rename Images
echo   ------------------------------------------------------------
echo.
echo   This renames the files in input\images so they sort in the
echo   order the video needs, oldest first:
echo.
echo     IMG_20260401_182233.jpg  -^>  001.jpg
echo     screenshot ^(10^).png      -^>  002.png
echo.
echo   It can put them in a different order first, by date, name,
echo   size, type or at random, forwards or backwards. It can also
echo   drop a new image into the middle: give it the picture and the
echo   number it should take, and everything from there shifts up.
echo.
echo   Filenames that are already numbered are left in that order,
echo   because those names are an order somebody chose and the date
echo   a file was copied onto this machine is not.
echo.
echo   It shows you the full list and asks again before renaming
echo   anything, and the old names can be put back with --undo.
echo   Only input\images is touched.
echo.
set "GO="
set /p "GO=  Press Enter to continue, or type N then Enter to cancel:  "
if /i "%GO%"=="N" goto :cancelled
if /i "%GO%"=="NO" goto :cancelled
:confirmed

rem Find a Python. The private copy that Setup.bat may have unpacked wins, so a
rem folder that was set up portably keeps working on a machine with no Python.
set "PY="
if exist "runtime\python\python.exe" set "PY=runtime\python\python.exe"

rem A Python on PATH only counts if it actually runs. A clean Windows keeps a
rem Microsoft Store stub called python.exe on the PATH, so "where python"
rem succeeds on a machine that has no Python at all, and running the stub opens
rem the Store instead of the script. Setup.bat has always tested the interpreter
rem by running it, and the launchers do the same now, so a folder copied to a
rem machine that was never set up says so instead of appearing to do nothing.
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

%PY% app\rename_images.py %FLAGS% %*
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

rem Reached only by the confirmation above. It sits past the exit so that the
rem normal path can never fall into it.
:cancelled
echo.
echo   Cancelled. No file was renamed and nothing was changed.
set "CODE=0"
goto :finish

