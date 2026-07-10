@echo off
set "LOG=%~dp0__pytest.txt"
echo === Direct python probe via absolute paths === > "%LOG%"

call :TRY "C:\Program Files\Python311\python.exe"
call :TRY "C:\Program Files\Python312\python.exe"
call :TRY "C:\Program Files\Python39\python.exe"
call :TRY "C:\Program Files (x86)\Python311\python.exe"
call :TRY "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :TRY "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :TRY "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
call :TRY "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
call :TRY "C:\Python311\python.exe"

echo. >> "%LOG%"
echo === PATH-based where.exe python === >> "%LOG%"
where.exe python >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo === DIR C:\Program Files directories starting with P === >> "%LOG%"
dir /B "C:\Program Files" 2>>&1 | findstr /I "^P" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo === DIR %LOCALAPPDATA%\Programs === >> "%LOG%"
dir /B "%LOCALAPPDATA%\Programs" >> "%LOG%" 2>&1

echo --- DONE --- >> "%LOG%"
type "%LOG%"
goto :eof

:TRY
if exist %~1 (
    echo [FOUND] %~1 >> "%LOG%"
    %~1 --version >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo          version probe FAILED with errorlevel=%errorlevel% >> "%LOG%"
    )
) else (
    echo [MISS ] %~1 >> "%LOG%"
)
goto :eof
