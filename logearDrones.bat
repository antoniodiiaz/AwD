@echo off
cd %~dp0

set "id=1 2 3 4 5 6 7 8 9 10 11 12 13 14 15"

for %%a in (%id%) do (
    start cmd /c python AD_DRONE.py registry::5000 localhost engine::8090 %%~a
    timeout /nobreak /t 1 >nul
)