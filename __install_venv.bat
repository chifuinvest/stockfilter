@echo off
setlocal
set "PY=C:\Users\Bart\AppData\Local\Programs\Python\Python314\python.exe"
set "VENV=%~dp0.venv"
set "PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple"
set "LOG=%~dp0__install_venv_log.txt"

echo ====================================================== > "%LOG%"
echo   Venv create + requirements install (TUNA mirror)     >> "%LOG%"
echo ====================================================== >> "%LOG%"
echo. >> "%LOG%"

echo [1/6] Python3.14 --version >> "%LOG%"
"%PY%" --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [2/6] Creating venv at %VENV% >> "%LOG%"
if exist "%VENV%\Scripts\python.exe" (
    echo   venv already exists, skip create. >> "%LOG%"
) else (
    "%PY%" -m venv "%VENV%" >> "%LOG%" 2>&1
    echo   venv create exitcode=%errorlevel% >> "%LOG%"
)
echo. >> "%LOG%"

echo [3/6] Venv python --version >> "%LOG%"
"%VENV%\Scripts\python.exe" --version >> "%LOG%" 2>&1
echo   venv python exitcode=%errorlevel% >> "%LOG%"
echo. >> "%LOG%"

echo [4/6] Upgrading pip via TUNA mirror >> "%LOG%"
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip -i "%PIP_INDEX%" --trusted-host pypi.tuna.tsinghua.edu.cn >> "%LOG%" 2>&1
echo   pip upgrade exitcode=%errorlevel% >> "%LOG%"
echo. >> "%LOG%"

echo [5/6] Installing requirements via TUNA mirror (2-10x faster!) >> "%LOG%"
"%VENV%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" -i "%PIP_INDEX%" --trusted-host pypi.tuna.tsinghua.edu.cn >> "%LOG%" 2>&1
set "RC=%errorlevel%"
echo   requirements install exitcode=%RC% >> "%LOG%"
echo. >> "%LOG%"

echo [6/6] Verifying streamlit inside venv >> "%LOG%"
"%VENV%\Scripts\python.exe" -m streamlit --version >> "%LOG%" 2>&1
echo   streamlit verify exitcode=%errorlevel% >> "%LOG%"
echo. >> "%LOG%"

echo ====================================================== >> "%LOG%"
echo   DONE. Final requirements exitcode=%RC% >> "%LOG%"
echo ====================================================== >> "%LOG%"

type "%LOG%"
exit /b %RC%
