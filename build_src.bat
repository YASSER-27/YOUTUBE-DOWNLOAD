@echo off
echo ==============================================
echo   Building Custom Engine (engine.exe) from src
echo ==============================================
pyinstaller --clean -y engine.spec
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] engine.exe built successfully in dist\engine.exe!
) else (
    echo.
    echo [ERROR] Failed to build engine.exe.
)
pause
