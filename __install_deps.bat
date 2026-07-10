@echo off
setlocal
set "PY=C:\Users\Bart\AppData\Local\Programs\Python\Python314\python.exe"
set "LAUNCH=C:\Users\Bart\AppData\Local\Programs\Python\Launcher\py.exe"
set "LOG=%~dp0__install_log.txt"

echo ====================================================== > "%LOG%"
echo   Python bootstrap + requirements install >> "%LOG%"
echo ====================================================== >> "%LOG%"
echo. >> "%LOG%"

echo [1/5] py launcher list all detected Pythons >> "%LOG%"
"%LAUNCH%" -0 >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [2/5] Python3.14 --version >> "%LOG%"
"%PY%" --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [3/5] Python3.14 pip --version >> "%LOG%"
"%PY%" -m pip --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [4/5] Upgrading pip >> "%LOG%"
"%PY%" -m pip install --upgrade pip >> "%LOG%" 2>&1
echo   pip upgrade exitcode=%errorlevel% >> "%LOG%"
echo. >> "%LOG%"

echo [5/5] Installing requirements.txt (this can take 5-15 min) >> "%LOG%"
"%PY%" -m pip install -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
set "RC=%errorlevel%"
echo   requirements install exitcode=%RC% >> "%LOG%"
echo. >> "%LOG%"

echo ====================================================== >> "%LOG%"
echo   DONE. Final exitcode=%RC% >> "%LOG%"
echo ====================================================== >> "%LOG%"

type "%LOG%"
exit /b %RC%
