@echo off
setlocal
set "PY=C:\Program Files\Python311\python.exe"
set "LOG=%~dp0__setup_log.txt"

echo === Python probe === > "%LOG%"
"%PY%" --version >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === pip --version === >> "%LOG%"
"%PY%" -m pip --version >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === Upgrading pip === >> "%LOG%"
"%PY%" -m pip install --upgrade pip >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === Install requirements === >> "%LOG%"
"%PY%" -m pip install -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
set "EXIT=%ERRORLEVEL%"
echo. >> "%LOG%"
echo === DONE, exitcode=%EXIT% === >> "%LOG%"
type "%LOG%"
exit /b %EXIT%
