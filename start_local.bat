@echo off
REM FloodCast backend — local laptop run (primary host; Render is fallback/demo mirror).
REM Run this file, leave the window open. DB persists in backend\Flood_prediction\.

cd /d %~dp0\backend
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  FloodCast backend starting on http://localhost:8000
echo  Health: http://localhost:8000/   Stations: http://localhost:8000/stations
echo  Leave this window OPEN. Close it to stop the backend.
echo ============================================================

python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
