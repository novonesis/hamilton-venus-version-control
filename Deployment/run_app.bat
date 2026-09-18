@echo off
:: Change directory to the location of this script (Deployment)
echo Attempting to change directory to script location...
cd /d "%~dp0"

:: Change to the project root directory to find pyproject.toml
echo Attempting to change to project root directory...
cd ..

:: Check if UV is available
echo Checking for UV availability...
uv --version
if %errorlevel% neq 0 goto uv_not_found
goto uv_found

:uv_not_found
echo UV not found. Please install UV (https://github.com/astral-sh/uv) and ensure it's in your PATH.
pause
exit /b 1

:uv_found

:: Create or synchronize the environment based on pyproject.toml
echo Synchronizing Python environment with uv...
echo Synchronizing Python environment with uv...
uv sync

:: Check if sync was successful
if %errorlevel% neq 0 (
    echo Failed to synchronize environment.
    echo Error code: %errorlevel%
    pause
    exit /b %errorlevel%
)

echo Environment synchronized. Running application...

:: Run the main Python script from the activated environment
:: Assuming the environment is created in ./.venv at the project root
echo Running the main Python script...
.\.venv\Scripts\python.exe .\Deployment\main.py

:: Keep window open if there was an error during application execution, otherwise close
if %errorlevel% neq 0 (
    echo Application finished with errors.
    echo Error code: %errorlevel%
    pause
) else (
    exit /b 0
)
pause