@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ==========================================================================
rem  img2vid setup.
rem
rem  Run this once on a new machine, then use Run.bat.
rem
rem  Nothing is installed system wide. Anything this script has to fetch goes
rem  inside this project folder and is removed if you delete the folder.
rem
rem    Python  : uses the system one if there is a suitable version on PATH,
rem              otherwise unpacks a private copy into .\runtime\python
rem    ffmpeg  : uses the system one if ffmpeg and ffprobe are on PATH,
rem              otherwise unpacks ffmpeg.exe and ffprobe.exe into .\bin
rem    speech  : installs the offline speech to text engine and its model
rem              into .\runtime\whisper, for Transcribe Audio.bat
rem
rem  Options:
rem    Setup.bat --local        ignore anything already on PATH, fetch both
rem                             locally, for a fully self contained folder
rem    Setup.bat --check        report what is installed and change nothing
rem    Setup.bat --no-transcribe  skip the speech engine, video assembly only
rem    Setup.bat --model small    pre-download a different size (tiny, base, small)
rem ==========================================================================

set "PYTHON_VERSION=3.12.10"
set "RUNTIME=%~dp0runtime"
set "PYDIR=%RUNTIME%\python"
set "BINDIR=%~dp0bin"
set "DL=%RUNTIME%\download"
set "WHISPERLIB=%RUNTIME%\whisper\lib"

set "LOCAL_ONLY="
set "CHECK_ONLY="
set "NO_SPEECH="
set "SPEECH_MODEL=base"
:parse_args
if "%~1"=="" goto :parsed
if /i "%~1"=="--local" set "LOCAL_ONLY=1"
if /i "%~1"=="--check" set "CHECK_ONLY=1"
if /i "%~1"=="--no-transcribe" set "NO_SPEECH=1"
if /i "%~1"=="--model" (
    set "SPEECH_MODEL=%~2"
    shift
)
shift
goto :parse_args
:parsed

rem Pause at the end only when double clicked.
set "HOLD="
echo %cmdcmdline% | find /i "%~nx0" >nul && set "HOLD=1"

echo.
echo   img2vid setup
echo   ============================================================
echo.

rem --------------------------------------------------------------------------
rem  Python
rem --------------------------------------------------------------------------
set "PY="
set "PYSOURCE="

if exist "%PYDIR%\python.exe" (
    set "PY=%PYDIR%\python.exe"
    set "PYSOURCE=local copy in runtime\python"
    goto :python_ready
)

if defined LOCAL_ONLY goto :python_install

rem A system Python only counts if it actually runs and is new enough. The
rem Microsoft Store stub on a clean Windows answers "where" but not much else.
for %%C in (python py) do (
    if not defined PY (
        %%C -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY=%%C"
            set "PYSOURCE=already on PATH"
        )
    )
)
if defined PY goto :python_ready

:python_install
if defined CHECK_ONLY (
    echo   [ ] Python      not found, would install locally
    goto :ffmpeg
)
echo   [.] Python      not usable on this machine, fetching a private copy
call :fetch "https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip" "%DL%\python.zip"
if errorlevel 1 (
    echo.
    echo   ERROR: could not download Python.
    echo   Check the internet connection, or install Python 3.8 or newer
    echo   from https://www.python.org/downloads/ and run this again.
    goto :finish
)
call :unzip "%DL%\python.zip" "%PYDIR%"
if not exist "%PYDIR%\python.exe" (
    echo   ERROR: the Python download did not unpack correctly.
    goto :finish
)
rem The embeddable build ships with site imports switched off, as a commented
rem out line. /b anchors the search to the start of a line so the commented
rem "#import site" is not mistaken for it already being enabled.
for %%F in ("%PYDIR%\python*._pth") do (
    findstr /b /c:"import site" "%%~F" >nul 2>&1 || echo import site>>"%%~F"
)
set "PY=%PYDIR%\python.exe"
set "PYSOURCE=downloaded into runtime\python"

:python_ready
if defined CHECK_ONLY (
    echo   [x] Python      %PYSOURCE%
) else (
    echo   [x] Python      %PYSOURCE%
)

rem --------------------------------------------------------------------------
rem  ffmpeg
rem --------------------------------------------------------------------------
:ffmpeg
set "FFSOURCE="

if exist "%BINDIR%\ffmpeg.exe" if exist "%BINDIR%\ffprobe.exe" (
    set "FFSOURCE=local copy in bin"
    goto :ffmpeg_ready
)

if defined LOCAL_ONLY goto :ffmpeg_install

where ffmpeg >nul 2>&1
if not errorlevel 1 (
    where ffprobe >nul 2>&1
    if not errorlevel 1 (
        set "FFSOURCE=already on PATH"
        goto :ffmpeg_ready
    )
)

:ffmpeg_install
if defined CHECK_ONLY (
    echo   [ ] ffmpeg      not found, would install locally
    goto :report
)
echo   [.] ffmpeg      not found on this machine, fetching a private copy
echo                   this one is around 90 MB, it may take a few minutes

set "FFZIP=%DL%\ffmpeg.zip"
call :fetch "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip" "%FFZIP%"
if errorlevel 1 call :fetch "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" "%FFZIP%"
if errorlevel 1 call :fetch "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" "%FFZIP%"
if errorlevel 1 (
    echo.
    echo   ERROR: could not download ffmpeg.
    echo   Check the internet connection, or download a Windows build yourself,
    echo   then copy ffmpeg.exe and ffprobe.exe into:
    echo     "%BINDIR%"
    goto :finish
)

call :unzip "%FFZIP%" "%DL%\ffmpeg"
if not exist "%BINDIR%" mkdir "%BINDIR%"
rem The archives nest the binaries a couple of folders deep, and the folder name
rem carries the build date, so search rather than assume a path.
for /r "%DL%\ffmpeg" %%F in (ffmpeg.exe ffprobe.exe) do (
    if exist "%%~fF" copy /y "%%~fF" "%BINDIR%\%%~nxF" >nul
)
if not exist "%BINDIR%\ffmpeg.exe" (
    echo   ERROR: the ffmpeg download did not contain ffmpeg.exe.
    goto :finish
)
set "FFSOURCE=downloaded into bin"

:ffmpeg_ready
echo   [x] ffmpeg      %FFSOURCE%

rem --------------------------------------------------------------------------
rem  Speech to text engine
rem
rem  Installed with pip --target rather than into a virtual environment. That is
rem  one code path for both the system Python and the embeddable one, which
rem  cannot host a normal venv because it ships without ensurepip.
rem --------------------------------------------------------------------------
:speech
if defined NO_SPEECH (
    echo   [ ] speech      skipped, --no-transcribe was given
    goto :report
)

if defined CHECK_ONLY (
    if exist "%WHISPERLIB%\faster_whisper" (
        echo   [x] speech      installed in runtime\whisper\lib
    ) else (
        echo   [ ] speech      not found, would install locally
    )
    goto :report
)

rem pip is what installs it, and the embeddable Python ships without pip.
"%PY%" -m pip --version >nul 2>&1
if not errorlevel 1 goto :speech_pip_ready
echo   [.] pip         not present, bootstrapping it into this folder only
call :fetch "https://bootstrap.pypa.io/get-pip.py" "%DL%\get-pip.py"
if errorlevel 1 goto :speech_failed
"%PY%" "%DL%\get-pip.py" --no-warn-script-location >nul 2>&1
"%PY%" -m pip --version >nul 2>&1
if errorlevel 1 goto :speech_failed

:speech_pip_ready
if exist "%WHISPERLIB%\faster_whisper" (
    echo   [x] speech      already installed in runtime\whisper\lib
) else (
    echo   [.] speech      installing the offline speech engine, around 140 MB
    "%PY%" -m pip install --no-warn-script-location --disable-pip-version-check --target "%WHISPERLIB%" faster-whisper
    if errorlevel 1 goto :speech_failed
    echo   [x] speech      installed into runtime\whisper\lib
)

echo   [.] model       checking for the %SPEECH_MODEL% model, downloaded once
"%PY%" setup_speech.py %SPEECH_MODEL%
if errorlevel 1 goto :speech_failed
echo   [x] model       %SPEECH_MODEL%, in runtime\whisper\models
goto :report

:speech_failed
echo   [!] speech      could not be installed, so Transcribe Audio.bat will not
echo                   run yet. Everything else works. Run Setup.bat again when
echo                   the connection is better, or use --no-transcribe.

rem --------------------------------------------------------------------------
rem  Verify
rem --------------------------------------------------------------------------
:report
if defined CHECK_ONLY (
    set "CODE=0"
    goto :finish
)

echo.
echo   checking that everything works together
echo.
"%PY%" setup_check.py
if errorlevel 1 (
    echo.
    echo   Setup did not pass its own check. See the message above.
    goto :finish
)

rem Free the download cache, the unpacked copies are what matter now.
if exist "%DL%" rmdir /s /q "%DL%" 2>nul

rem Create the folders the instructions below tell the user to fill in. They are
rem gitignored, so a fresh clone or a downloaded zip does not contain them, and
rem being told to open a folder that is not there is a poor first impression.
if not exist "%~dp0input\audio" mkdir "%~dp0input\audio" 2>nul
if not exist "%~dp0input\images" mkdir "%~dp0input\images" 2>nul
if not exist "%~dp0output" mkdir "%~dp0output" 2>nul

echo.
echo   ============================================================
echo   Setup complete. Nothing was installed system wide.
echo.
echo   Next:
echo     1. put your narration in  input\audio\
echo     2. run Transcribe Audio.bat
echo          writes input\script.srt and tells you how many images you need
echo     3. put that many images in  input\images\  named 1, 2, 3 ...
echo     4. run Create Video.bat
echo          the finished video appears in  output\
echo.
echo   Already have a transcript? Put it in input\ and skip step 2.
echo   ============================================================
set "CODE=0"
goto :finish

rem --------------------------------------------------------------------------
rem  Helpers
rem --------------------------------------------------------------------------
:fetch
rem %1 url, %2 destination. curl ships with Windows 10 and later and can resume
rem a part finished download, so it is tried first.
if not exist "%DL%" mkdir "%DL%" >nul 2>&1
where curl >nul 2>&1
if not errorlevel 1 (
    curl -L -f -# -C - --retry 3 --retry-delay 2 -o %2 %1
    if not errorlevel 1 exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri %1 -OutFile %2 -UseBasicParsing -TimeoutSec 900; exit 0 } catch { exit 1 }"
exit /b %ERRORLEVEL%

:unzip
rem %1 archive, %2 destination folder.
if exist %2 rmdir /s /q %2 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Expand-Archive -LiteralPath %1 -DestinationPath %2 -Force; exit 0 } catch { exit 1 }"
exit /b %ERRORLEVEL%

:finish
if not defined CODE set "CODE=1"
if defined HOLD (
    echo.
    pause
)
exit /b %CODE%
