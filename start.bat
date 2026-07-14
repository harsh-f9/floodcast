@echo off
setlocal
set PYTHONIOENCODING=utf-8

echo Starting CRO Website...
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

if not exist "%PYTHON%" (
	where py >nul 2>nul
	if not errorlevel 1 (
		py -3 -m venv "%VENV%"
	) else (
		where python >nul 2>nul
		if not errorlevel 1 (
			python -m venv "%VENV%"
		) else (
			echo Python 3 was not found on PATH.
			exit /b 1
		)
	)
)

if not exist "%PYTHON%" (
	echo Failed to create the virtual environment.
	exit /b 1
)

"%PYTHON%" -m pip show fastapi >nul 2>nul
if errorlevel 1 (
	"%PYTHON%" -m pip install -r "%BACKEND%\requirements.txt"
	if errorlevel 1 (
		echo Failed to install backend dependencies.
		exit /b 1
	)
)

:: Start FastAPI backend in a new window (port 8000)
start "CRO Backend" "%PYTHON%" -m uvicorn main:app --reload --port 8000 --app-dir "%BACKEND%"

:: Wait a moment for the backend to boot, then start frontend
ping 127.0.0.1 -n 3 >nul

:: Start frontend
start "CRO Frontend" cmd /k "npm run dev"

:: Wait for Vite to boot, then open the browser
ping 127.0.0.1 -n 4 >nul
start http://localhost:8080
