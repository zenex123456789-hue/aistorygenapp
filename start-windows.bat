@echo off
rem  AI Story Factory launcher for Windows.
rem    start-windows.bat         runs the app on this PC       (http://127.0.0.1:8000)
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set PYTHONUTF8=1
title AI Story Factory

rem --- FFmpeg: FFMPEG_BIN if already set, else PATH, else an unzipped build in your user folder
if not defined FFMPEG_BIN (
  where ffmpeg >nul 2>&1
  if errorlevel 1 (
    for /d %%d in ("%USERPROFILE%\ffmpeg*") do (
      if exist "%%d\bin\ffmpeg.exe" (
        set "FFMPEG_BIN=%%d\bin\ffmpeg.exe"
        set "FFPROBE_BIN=%%d\bin\ffprobe.exe"
      )
      for /d %%e in ("%%d\*") do if exist "%%e\bin\ffmpeg.exe" (
        set "FFMPEG_BIN=%%e\bin\ffmpeg.exe"
        set "FFPROBE_BIN=%%e\bin\ffprobe.exe"
      )
    )
  )
)
if defined FFMPEG_BIN echo FFmpeg: %FFMPEG_BIN%

rem --- Python 3.10+
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Could not find Python 3.10 or newer. Install it from python.org first.
  pause
  exit /b 1
)
echo Using: %PY%

echo.
echo Installing packages (the first run takes a minute)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo pip install failed. Scroll up to see why.
  pause
  exit /b 1
)

echo.
echo Starting AI Story Factory. Your browser will open at http://127.0.0.1:8000
echo Leave this window open while you use it. Close it to stop the app.
start "" /b cmd /c "timeout /t 6 /nobreak >nul && start http://127.0.0.1:8000"
%PY% run.py
echo.
echo The app stopped.
pause
