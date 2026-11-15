@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating the project environment...
  python -m venv .venv
  if errorlevel 1 goto failed
)

call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 goto failed

if not exist ".env" copy ".env.example" ".env" >nul
python seed.py
if errorlevel 1 goto failed

echo.
echo Starting Orbit Hire at http://127.0.0.1:5000
python -m flask --app app run
goto finished

:failed
echo.
echo The project could not start. Review the error above and check README.md.
pause

:finished
endlocal
