@echo off
setlocal enabledelayedexpansion
set "LOG=%~dp0__pywhere.txt"
echo Scanning Python install locations... > "%LOG%"
echo. >> "%LOG%"
set "PY="

call :CHECK "C:\Program Files\Python311\python.exe"
call :CHECK "C:\Program Files (x86)\Python311\python.exe"
call :CHECK "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :CHECK "%APPDATA%\Programs\Python\Python311\python.exe"
call :CHECK "C:\Python311\python.exe"
call :CHECK "C:\Program Files\Python312\python.exe"
call :CHECK "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :CHECK "C:\Program Files\Python310\python.exe"
call :CHECK "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
call :CHECK "C:\Program Files\Python39\python.exe"
call :CHECK "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

echo. >> "%LOG%"
if defined PY (
    echo FINAL_SELECTED=%PY% >> "%LOG%"
    echo. >> "%LOG%"
    echo [Probe version] >> "%LOG%"
    "%PY%" --version >> "%LOG%" 2>&1
    "%PY%" -m pip --version >> "%LOG%" 2>&1
) else (
    echo NO_PY_FOUND_IN_STANDARD_PATHS >> "%LOG%"
)
echo --- DONE --- >> "%LOG%"
type "%LOG%"
goto :eof

:CHECK
if exist %~1 (
    echo FOUND: %~1 >> "%LOG%"
    if not defined PY set "PY=%~1"
) else (
    echo MISS:  %~1 >> "%LOG%"
)
goto :eof
