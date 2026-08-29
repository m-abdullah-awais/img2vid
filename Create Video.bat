@echo off
setlocal
cd /d "%~dp0"

rem The folders the instructions in this file point at. Setup.bat creates them
rem too, but they are gitignored and git cannot carry an empty folder, so a copy
rem that was cloned or unzipped and never set up has none of them. Making them
rem here as well means a user is never told to open a folder that is not there.
for %%D in ("input\audio" "input\images" "output") do if not exist "%%~D" mkdir "%%~D" 2>nul

rem ==========================================================================
rem  Step 2 of 2.  Transcript + images + audio  ->  finished MP4.
rem
rem  Expects:
rem    input\script.srt      a timestamped transcript, or run Transcribe Audio.bat
rem    input\images\         one image per transcript line, in name order
rem    input\audio\          one or more audio files
rem
rem  The video is written to output\ and named for the date and time it was
rem  built, so a second attempt never replaces the first.
rem
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

rem --------------------------------------------------------------------------
rem  Ask before doing anything, so opening this by mistake costs nothing.
rem  Only when it was double clicked. From a terminal or a script it is
rem  deliberate and goes straight through, so automation is unaffected. Closing
rem  the window cancels, and so does typing N.
rem --------------------------------------------------------------------------
if not defined HOLD goto :confirmed
echo.
echo   Create Video
echo   ------------------------------------------------------------
echo.
echo   This builds the finished video from what is in the input
echo   folder:
echo.
echo     input\script.srt      the transcript, one line per image
echo     input\images\         your images, in filename order
echo     input\audio\          your narration
echo.
echo   The video is written to output\ and replaces any file there
echo   with the same name. Expect a minute or two for a ten minute
echo   video, and most of the processor to be busy while it runs.
echo.
set "GO="
set /p "GO=  Press Enter to start, or type N then Enter to cancel:  "
if /i "%GO%"=="N" goto :cancelled
if /i "%GO%"=="NO" goto :cancelled
:confirmed

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

%PY% app\run.py %FLAGS% %*
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

rem Reached only by the confirmation above. It sits past the exit so that the
rem normal path can never fall into it.
:cancelled
echo.
echo   Cancelled. No video was built and nothing was changed.
set "CODE=0"
goto :finish

