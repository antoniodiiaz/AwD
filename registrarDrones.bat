@echo off
cd %~dp0

set /p repeticiones="Ingrese el numero de drones: "

for /l %%i in (1,1,%repeticiones%) do (
	start cmd /c python ../AD_DRONE.py registry::8000 localhost engine::8080
	
)