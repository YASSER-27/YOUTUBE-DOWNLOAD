@echo off
echo ==============================================
echo   Step 1: Building engine.exe from src
echo ==============================================
pyinstaller --clean -y engine.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] engine.exe build failed. Aborting.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==============================================
echo   Step 2: Building Main App (Download Free.exe)
echo ==============================================
pyinstaller --clean -y app.spec
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================
    echo   [SUCCESS] Build complete!
    echo   Executable is ready in: dist\Download Free.exe
    echo ==============================================
) else (
    echo.
    echo [ERROR] Main app build failed.
)
pause
