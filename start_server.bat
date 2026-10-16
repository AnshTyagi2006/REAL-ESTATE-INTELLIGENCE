@echo off
setlocal
cd /d "%~dp0"
python src\api\valuation_api.py
if errorlevel 1 (
  echo.
  echo The server stopped because an error occurred.
  pause
)
endlocal
