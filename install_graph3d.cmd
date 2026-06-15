@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
cd /d "%ROOT%" || exit /b 1

echo graph3d local production install
echo Repository: %CD%

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
    set "PYTHON_SCRIPTS=%ROOT%.venv\Scripts"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo ERROR: python was not found on PATH and .venv\Scripts\python.exe does not exist.
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Python: %PYTHON_EXE%

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: graph3d requires Python 3.10 or newer.
    "%PYTHON_EXE%" --version
    exit /b 1
)

"%PYTHON_EXE%" -c "import build" >nul 2>nul
if errorlevel 1 (
    echo Installing Python build backend helper...
    "%PYTHON_EXE%" -m pip install --upgrade build
    if errorlevel 1 exit /b 1
)

if not exist "dist" mkdir "dist"
del /q "dist\graph3d-*.whl" >nul 2>nul
del /q "dist\graph3d-*.tar.gz" >nul 2>nul

echo Building Python wheel and source distribution...
"%PYTHON_EXE%" -m build --wheel --sdist --outdir "dist"
if errorlevel 1 exit /b 1

set "WHEEL="
for /f "delims=" %%F in ('dir /b /o-d "dist\graph3d-*.whl" 2^>nul') do (
    if not defined WHEEL set "WHEEL=dist\%%F"
)

if not defined WHEEL (
    echo ERROR: no graph3d wheel was produced in dist.
    exit /b 1
)

echo Installing local wheel: %WHEEL%
"%PYTHON_EXE%" -m pip install --force-reinstall --no-deps "%WHEEL%"
if errorlevel 1 exit /b 1

if not defined PYTHON_SCRIPTS (
    for /f "delims=" %%P in ('python -c "import sysconfig; print(sysconfig.get_path(chr(115)+chr(99)+chr(114)+chr(105)+chr(112)+chr(116)+chr(115)))"') do set "PYTHON_SCRIPTS=%%P"
)
if defined PYTHON_SCRIPTS set "PATH=%PYTHON_SCRIPTS%;%PATH%"

echo Validating installed Python package...
"%PYTHON_EXE%" -c "import graph3d, importlib.metadata as md; print('graph3d python package', md.version('graph3d'), graph3d.__file__)"
if errorlevel 1 exit /b 1

"%PYTHON_EXE%" -m graph3d --version
if errorlevel 1 exit /b 1

"%PYTHON_EXE%" -m pip check
if errorlevel 1 exit /b 1

where graph3d >nul 2>nul
if errorlevel 1 (
    echo WARNING: graph3d console launcher is installed, but its Scripts directory is not on PATH for this terminal.
) else (
    graph3d --version
    if errorlevel 1 exit /b 1
)

if exist "package.json" (
    echo package.json found; validating npm package...
    where npm >nul 2>nul
    if errorlevel 1 (
        echo ERROR: npm package metadata exists, but npm was not found on PATH.
        exit /b 1
    )
    call npm install
    if errorlevel 1 exit /b 1
    call npm run build --if-present
    if errorlevel 1 exit /b 1
    call npm test
    if errorlevel 1 exit /b 1
    call npm run npx:smoke
    if errorlevel 1 exit /b 1
    call npm pack --dry-run
    if errorlevel 1 exit /b 1
) else (
    echo NOTE: npm package validation skipped because no package.json exists in the repository root.
)

echo graph3d install validation complete.
endlocal
