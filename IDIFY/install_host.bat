@echo off
setlocal

set "DIR=%~dp0"
set "MANIFEST_PATH=%DIR%com.vidjo.idify.json"
set "HOST_BAT=%DIR%host.bat"

echo @echo off> "%HOST_BAT%"
echo "%%~dp0venv\Scripts\python.exe" "%%~dp0host.py" %%*>> "%HOST_BAT%"

echo {> "%MANIFEST_PATH%"
echo   "name": "com.vidjo.idify",>> "%MANIFEST_PATH%"
echo   "description": "IDIFY Native Messaging Host",>> "%MANIFEST_PATH%"
echo   "path": "%DIR:\=\\%host.bat",>> "%MANIFEST_PATH%"
echo   "type": "stdio",>> "%MANIFEST_PATH%"
echo   "allowed_extensions": [ "idify@vidjo.com" ],>> "%MANIFEST_PATH%"
echo   "allowed_origins": [ "chrome-extension://*/*" ]>> "%MANIFEST_PATH%"
echo }>> "%MANIFEST_PATH%"

echo Registering Native Messaging Host for Firefox...
REG ADD "HKCU\Software\Mozilla\NativeMessagingHosts\com.vidjo.idify" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f

echo Registering Native Messaging Host for Chrome...
REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vidjo.idify" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f

echo.
echo Installed successfully! You can close this window.
pause
