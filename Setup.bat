@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ==========================================================================
rem  img2vid setup.
rem
rem  Run this once on a new machine, then double click Run.bat.
rem
rem  Nothing is installed system wide. Anything this script has to fetch goes
rem  inside backend\runtime in this project folder and is removed if you delete
rem  the folder.
rem
rem    Python  : uses the system one if there is a suitable version on PATH,
rem              otherwise unpacks a private copy into backend\runtime\python
rem    ffmpeg  : uses the system one if ffmpeg and ffprobe are on PATH,
rem              otherwise unpacks ffmpeg.exe and ffprobe.exe into
rem              backend\runtime\bin
rem    Node.js : uses the system one if Node 20 or newer is on PATH, otherwise
rem              unpacks a private copy into backend\runtime\node
rem    web app : installs the web app's packages into frontend\node_modules
rem              and builds it, so the first Run.bat opens quickly
rem    speech  : installs the offline speech to text engine and its model
rem              into backend\runtime\whisper, for transcribing narration
rem
rem  Options:
rem    Setup.bat --local        ignore anything already on PATH, fetch all of it
rem                             locally, for a fully self contained folder
rem    Setup.bat --check        report what is installed and change nothing
rem    Setup.bat --no-transcribe  skip the speech engine, video assembly only
rem    Setup.bat --model small    pre-download a different size (tiny, base, small)
rem ==========================================================================

set "PYTHON_VERSION=3.12.10"
set "NODE_VERSION=24.11.0"
set "RUNTIME=%~dp0backend\runtime"
set "PYDIR=%RUNTIME%\python"
set "BINDIR=%RUNTIME%\bin"
set "NODEDIR=%RUNTIME%\node"
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

rem --------------------------------------------------------------------------
rem  Ask before doing anything, so opening this by mistake costs nothing.
rem
rem  Only when it was double clicked. Started from a terminal or another script
rem  it is deliberate and goes straight through, which keeps it usable from a
rem  command line and in automation. --check changes nothing, so it never asks.
rem
rem  Closing the window cancels, and so does typing N.
rem --------------------------------------------------------------------------
if not defined HOLD goto :confirmed
if defined CHECK_ONLY goto :confirmed
echo.
echo   img2vid setup
echo   ============================================================
echo.
echo   This prepares img2vid in this folder. It will:
echo.
echo     - install Python, ffmpeg and Node.js here, only if they are missing
echo     - install and build the web app
echo     - install the offline speech engine and its model
echo.
echo   The first run downloads up to about 450 MB, and only what this
echo   machine is actually missing.
echo.
echo   Nothing is installed system wide, and nothing outside this folder
echo   is touched. Deleting the folder removes every trace.
echo.
set "GO="
set /p "GO=  Press Enter to start, or type N then Enter to cancel:  "
if /i "%GO%"=="N" goto :cancelled
if /i "%GO%"=="NO" goto :cancelled
:confirmed

echo.
echo   img2vid setup
echo   ============================================================
echo.

rem Explorer will run a batch file straight out of a zip by unpacking it to a
rem temporary folder, and everything created there is discarded on the way out.
rem From the outside that looks exactly like Setup having done nothing at all.
set "HERE=%~dp0"
if not "!HERE:\AppData\Local\Temp\=!"=="!HERE!" (
    echo   ERROR: this copy is running from inside a zip file.
    echo.
    echo   Windows unpacked it into a temporary folder, so anything set up here
    echo   is thrown away again as soon as it finishes.
    echo.
    echo   Right click the zip, choose Extract All, pick a normal folder such as
    echo   Documents, and run Setup.bat from there.
    goto :finish
)

rem A copy set up before the web app kept its private Python, ffmpeg and speech
rem engine in runtime\ and bin\ at the top of the folder. They are moved into
rem backend\runtime rather than downloaded again, which on a slow connection is
rem most of what this script would otherwise spend its time on.
if not defined CHECK_ONLY call :adopt_old_folders

rem --------------------------------------------------------------------------
rem  Python
rem --------------------------------------------------------------------------
set "PY="
set "PYSOURCE="

if exist "%PYDIR%\python.exe" (
    set "PY=%PYDIR%\python.exe"
    set "PYSOURCE=local copy in backend\runtime\python"
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
if errorlevel 1 (
    echo.
    echo   ERROR: the Python download arrived but could not be unpacked.
    echo   It is most likely incomplete. Run Setup.bat again, or install
    echo   Python 3.8 or newer from https://www.python.org/downloads/.
    goto :finish
)
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
set "PYSOURCE=downloaded into backend\runtime\python"

:python_ready
echo   [x] Python      %PYSOURCE%

rem --------------------------------------------------------------------------
rem  ffmpeg
rem --------------------------------------------------------------------------
:ffmpeg
set "FFSOURCE="

if exist "%BINDIR%\ffmpeg.exe" if exist "%BINDIR%\ffprobe.exe" (
    set "FFSOURCE=local copy in backend\runtime\bin"
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
    goto :node
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
if errorlevel 1 (
    echo.
    echo   ERROR: the ffmpeg download arrived but could not be unpacked.
    echo   It is most likely incomplete. Run Setup.bat again, and if it stops
    echo   here a second time, download a Windows build of ffmpeg yourself and
    echo   copy ffmpeg.exe and ffprobe.exe into:
    echo     "%BINDIR%"
    goto :finish
)

if not exist "%BINDIR%" mkdir "%BINDIR%"
rem The archives nest the binaries a couple of folders deep, and the folder name
rem carries the build date, so search rather than assume a path.
for /r "%DL%\ffmpeg" %%F in (ffmpeg.exe ffprobe.exe) do (
    if exist "%%~fF" copy /y "%%~fF" "%BINDIR%\%%~nxF" >nul
)
rem Both are needed. The renderer calls ffmpeg, and every duration and frame
rem count it works from comes out of ffprobe.
if not exist "%BINDIR%\ffmpeg.exe" goto :ffmpeg_missing
if not exist "%BINDIR%\ffprobe.exe" goto :ffmpeg_missing
goto :ffmpeg_copied

:ffmpeg_missing
echo.
echo   ERROR: the ffmpeg download did not contain ffmpeg.exe and ffprobe.exe.
echo   Download a Windows build from https://www.gyan.dev/ffmpeg/builds/ and
echo   copy both files into:
echo     "%BINDIR%"
goto :finish

:ffmpeg_copied
set "FFSOURCE=downloaded into backend\runtime\bin"

:ffmpeg_ready
echo   [x] ffmpeg      %FFSOURCE%

rem --------------------------------------------------------------------------
rem  Node.js, which serves the web app
rem --------------------------------------------------------------------------
:node
set "NODE="
set "NODESOURCE="

if exist "%NODEDIR%\node.exe" (
    set "NODE=%NODEDIR%\node.exe"
    set "NODESOURCE=local copy in backend\runtime\node"
    goto :node_ready
)

if defined LOCAL_ONLY goto :node_install

rem Next.js needs Node 20 or newer, so an older one on PATH counts as missing
rem rather than failing later with an error that names neither Node nor Next.
node -e "process.exit(+process.versions.node.split('.')[0]>=20?0:1)" >nul 2>&1
if not errorlevel 1 (
    set "NODE=node"
    set "NODESOURCE=already on PATH"
    goto :node_ready
)

:node_install
if defined CHECK_ONLY (
    echo   [ ] Node.js     not found, would install locally
    goto :webapp
)
echo   [.] Node.js     not found on this machine, fetching a private copy
echo                   this one is around 35 MB
call :fetch "https://nodejs.org/dist/v%NODE_VERSION%/node-v%NODE_VERSION%-win-x64.zip" "%DL%\node.zip"
if errorlevel 1 (
    echo.
    echo   ERROR: could not download Node.js.
    echo   Check the internet connection, or install Node.js 20 or newer from
    echo   https://nodejs.org/ and run this again.
    goto :finish
)
call :unzip "%DL%\node.zip" "%DL%\node"
if errorlevel 1 (
    echo.
    echo   ERROR: the Node.js download arrived but could not be unpacked.
    echo   It is most likely incomplete. Run Setup.bat again.
    goto :finish
)
if exist "%NODEDIR%" rmdir /s /q "%NODEDIR%" 2>nul
rem The archive holds one folder named for the version, with node.exe inside.
move "%DL%\node\node-v%NODE_VERSION%-win-x64" "%NODEDIR%" >nul 2>&1
if not exist "%NODEDIR%\node.exe" (
    echo   ERROR: the Node.js download did not unpack correctly.
    goto :finish
)
set "NODE=%NODEDIR%\node.exe"
set "NODESOURCE=downloaded into backend\runtime\node"

:node_ready
echo   [x] Node.js     %NODESOURCE%

rem --------------------------------------------------------------------------
rem  The web app
rem
rem  Its packages go in frontend\node_modules and npm's download cache goes in
rem  backend\runtime\npm-cache, so nothing lands in the user profile. Building
rem  it here means the first Run.bat opens in seconds instead of a minute.
rem --------------------------------------------------------------------------
:webapp
if not exist "%~dp0frontend\package.json" goto :speech

if defined CHECK_ONLY (
    if exist "%~dp0frontend\.next\BUILD_ID" (
        echo   [x] web app     installed and built
    ) else (
        echo   [ ] web app     not built yet, would install and build it
    )
    goto :speech
)

if /i "%NODE%"=="%NODEDIR%\node.exe" set "PATH=%NODEDIR%;%PATH%"
set "npm_config_cache=%RUNTIME%\npm-cache"
set "NEXT_TELEMETRY_DISABLED=1"
set "WEBAPP_OK="
pushd "%~dp0frontend"
echo   [.] web app     installing its packages
call npm ci --no-audit --no-fund --loglevel=error
if not errorlevel 1 (
    echo   [.] web app     building it, about a minute the first time
    call npm run build
    if not errorlevel 1 set "WEBAPP_OK=1"
)
popd
if not defined WEBAPP_OK (
    echo.
    echo   ERROR: the web app could not be installed or built. See the message
    echo   above. Run Setup.bat again when the connection is better.
    goto :finish
)
echo   [x] web app     installed and built

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
        echo   [x] speech      installed in backend\runtime\whisper\lib
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
    echo   [x] speech      already installed in backend\runtime\whisper\lib
) else (
    echo   [.] speech      installing the offline speech engine, around 140 MB
    "%PY%" -m pip install --no-warn-script-location --disable-pip-version-check --target "%WHISPERLIB%" faster-whisper
    if errorlevel 1 goto :speech_failed
    echo   [x] speech      installed into backend\runtime\whisper\lib
)

echo   [.] model       checking for the %SPEECH_MODEL% model, downloaded once
"%PY%" backend\cli\setup_speech.py %SPEECH_MODEL%
if errorlevel 1 goto :speech_failed
echo   [x] model       %SPEECH_MODEL%, in backend\runtime\whisper\models
goto :report

:speech_failed
echo   [!] speech      could not be installed, so transcribing narration will
echo                   not work yet. Everything else works. Run Setup.bat again
echo                   when the connection is better, or use --no-transcribe.

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
"%PY%" backend\cli\setup_check.py
if errorlevel 1 (
    echo.
    echo   Setup did not pass its own check. See the message above.
    goto :finish
)

rem Free the download cache, the unpacked copies are what matter now.
if exist "%DL%" rmdir /s /q "%DL%" 2>nul

echo.
echo   ============================================================
echo   Setup complete. Nothing was installed system wide.
echo.
echo   Next: double click Run.bat. img2vid opens in your browser, and
echo   everything from uploading narration to downloading the finished
echo   video happens there.
echo   ============================================================
set "CODE=0"
goto :finish

rem --------------------------------------------------------------------------
rem  Helpers
rem --------------------------------------------------------------------------
:adopt_old_folders
if exist "%~dp0runtime\" if not exist "%RUNTIME%\" (
    move "%~dp0runtime" "%RUNTIME%" >nul 2>&1
    if exist "%RUNTIME%\" echo   [x] moved       runtime\ into backend\runtime
)
if exist "%~dp0bin\ffmpeg.exe" if not exist "%BINDIR%\ffmpeg.exe" (
    if not exist "%BINDIR%" mkdir "%BINDIR%"
    for %%F in (ffmpeg.exe ffprobe.exe) do (
        if exist "%~dp0bin\%%F" move "%~dp0bin\%%F" "%BINDIR%\%%F" >nul 2>&1
    )
    rmdir "%~dp0bin" 2>nul
    if exist "%BINDIR%\ffmpeg.exe" echo   [x] moved       bin\ into backend\runtime\bin
)
exit /b 0

:fetch
rem %1 url, %2 destination. curl ships with Windows 10 and later, so it is tried
rem first and powershell is the fallback.
rem
rem The two arguments are put into the environment before powershell is called
rem rather than written into its command line. powershell.exe takes one layer of
rem quoting off whatever follows -Command, so a quoted path arrives there as
rem several separate arguments and the call fails on the first space. Every path
rem in this project has a space in it, the folder is called "Images to Video".
set "DL_URL=%~1"
set "DL_OUT=%~2"
if not exist "%DL%" mkdir "%DL%" >nul 2>&1

rem Anything left behind by an earlier attempt is deleted rather than resumed.
rem The callers work through several different addresses in turn, so resuming
rem would append the start of one archive onto the middle of another and produce
rem a file that looks complete and cannot be unpacked.
if exist "%DL_OUT%" del /f /q "%DL_OUT%" >nul 2>&1

where curl >nul 2>&1
if not errorlevel 1 (
    curl -L -f -# --retry 3 --retry-delay 2 -o "%DL_OUT%" "%DL_URL%"
    if not errorlevel 1 if exist "%DL_OUT%" exit /b 0
    if exist "%DL_OUT%" del /f /q "%DL_OUT%" >nul 2>&1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri $env:DL_URL -OutFile $env:DL_OUT -UseBasicParsing -TimeoutSec 900; exit 0 } catch { Write-Host ('                  ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 exit /b 1
if not exist "%DL_OUT%" exit /b 1
exit /b 0

:unzip
rem %1 archive, %2 destination folder. The paths travel in the environment for
rem the same reason as in :fetch above.
set "ZIP_SRC=%~1"
set "ZIP_DST=%~2"
if exist "%ZIP_DST%" rmdir /s /q "%ZIP_DST%" 2>nul
mkdir "%ZIP_DST%" 2>nul

rem tar has shipped with Windows since 2018 and reads zip files. It is tried
rem first because it unpacks the 90 MB ffmpeg archive in seconds where
rem Expand-Archive takes minutes. A half unpacked folder from a failed attempt
rem is cleared out before the fallback runs, so the fallback starts clean.
where tar >nul 2>&1
if not errorlevel 1 (
    tar -xf "%ZIP_SRC%" -C "%ZIP_DST%" 2>nul
    if not errorlevel 1 exit /b 0
    rmdir /s /q "%ZIP_DST%" 2>nul
    mkdir "%ZIP_DST%" 2>nul
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Expand-Archive -LiteralPath $env:ZIP_SRC -DestinationPath $env:ZIP_DST -Force; exit 0 } catch { Write-Host ('                  ' + $_.Exception.Message); exit 1 }"
exit /b %ERRORLEVEL%

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
echo   Cancelled. Nothing was installed and nothing was changed.
set "CODE=0"
goto :finish
