@echo off
setlocal
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "LOG=%~dp0__install_default_log.txt"

echo ====================================================== > "%LOG%"
echo   Requirements install via DEFAULT PyPI (no mirror)    >> "%LOG%"
echo   Long timeout (300s) + 10 retries for slow links      >> "%LOG%"
echo ====================================================== >> "%LOG%"
echo. >> "%LOG%"

echo [1/3] Venv python --version >> "%LOG%"
"%PY%" --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [2/3] pip list (check what we have) >> "%LOG%"
"%PY%" -m pip list >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo [3/3] Installing requirements (SLOW but STABLE - 15~30min, please wait) >> "%LOG%"
"%PY%" -m pip install --default-timeout=300 --retries 10 -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
set "RC=%errorlevel%"
echo   requirements install exitcode=%RC% >> "%LOG%"
echo. >> "%LOG%"

echo [VERIFY] streamlit version inside venv: >> "%LOG%"
"%PY%" -m streamlit --version >> "%LOG%" 2>&1
echo   streamlit exitcode=%errorlevel% >> "%LOG%"
echo. >> "%LOG%"

echo ====================================================== >> "%LOG%"
echo   DONE. Final exitcode=%RC% >> "%LOG%"
echo ====================================================== >> "%LOG%"

type "%LOG%"
exit /b %RC%
