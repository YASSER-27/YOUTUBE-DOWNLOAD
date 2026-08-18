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
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Main app build failed. Aborting.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==============================================
echo   Step 3: Compiling Installer with Inno Setup
echo ==============================================
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "installer.iss"
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================
    echo   [SUCCESS] All Complete!
    echo   Installer: Output\DownloadFree_Setup_v2.0.exe
    echo   Standalone: dist\Download Free.exe
    echo ==============================================
) else (
    echo.
    echo [WARNING] Inno Setup compilation failed or not found.
)
pause
