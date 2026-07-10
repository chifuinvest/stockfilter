@echo off
set "LOG=%~dp0__pdirs.txt"
echo === LOCALAPPDATA Programs Python directory === > "%LOG%"
dir /S /B "%LOCALAPPDATA%\Programs\Python\python.exe" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === LOCALAPPDATA Programs Python subdirs === >> "%LOG%"
dir /B "%LOCALAPPDATA%\Programs\Python" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === C:\Program Files dirs starting with P (Python, etc) === >> "%LOG%"
dir /B "C:\Program Files" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === Direct call with quoted path test === >> "%LOG%"
set "PY1=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if exist "%PY1%" (
    echo py.exe FOUND: %PY1% >> "%LOG%"
    "%PY1%" --version >> "%LOG%" 2>&1
    "%PY1%" -3.11 --version >> "%LOG%" 2>&1
    "%PY1%" -3.12 --version >> "%LOG%" 2>&1
    "%PY1%" -3.9  --version >> "%LOG%" 2>&1
) else (
    echo py.exe MISS >> "%LOG%"
)
echo. >> "%LOG%"
echo === where pythonw.exe py.exe === >> "%LOG%"
where.exe pythonw.exe >> "%LOG%" 2>&1
where.exe py.exe >> "%LOG%" 2>&1
echo --- DONE --- >> "%LOG%"
type "%LOG%"
