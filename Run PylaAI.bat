@echo off
setlocal
cd /d %~dp0

py -3.11-64 tools\runtime_preflight.py
if errorlevel 2 goto repair
if errorlevel 1 goto python_error
goto start

:repair
echo.
echo Repairing PylaAI dependencies. This can take a few minutes...
set PYLAAI_SETUP_AUTO=1
py -3.11-64 setup.py install
if errorlevel 1 goto repair_failed

py -3.11-64 tools\runtime_preflight.py
if errorlevel 1 goto repair_failed
goto start

:python_error
echo.
echo Python 3.11 64-bit was not found. Run setup.exe, then start PylaAI again.
pause
exit /b 1

:repair_failed
echo.
echo PylaAI dependencies could not be repaired automatically.
echo Install Microsoft Visual C++ Redistributable 2015-2022 x64:
echo https://aka.ms/vs/17/release/vc_redist.x64.exe
echo Then restart Windows and run this file again.
pause
exit /b 1

:start
py -3.11-64 main.py
pause
