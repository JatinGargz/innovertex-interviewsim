@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating the local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 goto failed
  echo Installing InterviewSim requirements...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)

powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Starting InterviewSim...
  start "InterviewSim server" /min ".venv\Scripts\python.exe" -m uvicorn interviewsim.app:app --host 127.0.0.1 --port 8000
)

for /l %%i in (1,1,30) do (
  powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
  if not errorlevel 1 goto ready
  timeout /t 1 /nobreak >nul
)
echo InterviewSim did not start. Check the server window for an error.
pause
exit /b 1

:ready
start "" "http://127.0.0.1:8000"
echo InterviewSim is open. Keep its server window running while you use it.
exit /b 0

:failed
echo Could not prepare InterviewSim. Install Python 3.11 or later and try again.
pause
exit /b 1
