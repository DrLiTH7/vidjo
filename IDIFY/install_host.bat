@echo off
setlocal

set "DIR=%~dp0"
set "MANIFEST_FIREFOX=%DIR%com.vidjo.idify.firefox.json"
set "MANIFEST_CHROME=%DIR%com.vidjo.idify.chrome.json"
set "HOST_BAT=%DIR%host.bat"

echo @echo off> "%HOST_BAT%"
echo "%%~dp0venv\Scripts\python.exe" "%%~dp0host.py" %%*>> "%HOST_BAT%"

echo {> "%MANIFEST_FIREFOX%"
echo   "name": "com.vidjo.idify",>> "%MANIFEST_FIREFOX%"
echo   "description": "IDIFY Native Messaging Host",>> "%MANIFEST_FIREFOX%"
echo   "path": "%DIR:\=\\%host.bat",>> "%MANIFEST_FIREFOX%"
echo   "type": "stdio",>> "%MANIFEST_FIREFOX%"
echo   "allowed_extensions": [ "idify@vidjo.com" ]>> "%MANIFEST_FIREFOX%"
echo }>> "%MANIFEST_FIREFOX%"

echo {> "%MANIFEST_CHROME%"
echo   "name": "com.vidjo.idify",>> "%MANIFEST_CHROME%"
echo   "description": "IDIFY Native Messaging Host",>> "%MANIFEST_CHROME%"
echo   "path": "%DIR:\=\\%host.bat",>> "%MANIFEST_CHROME%"
echo   "type": "stdio",>> "%MANIFEST_CHROME%"
echo   "allowed_origins": [ "chrome-extension://*/*" ]>> "%MANIFEST_CHROME%"
echo }>> "%MANIFEST_CHROME%"

echo Registering Native Messaging Host for Firefox...
REG ADD "HKCU\Software\Mozilla\NativeMessagingHosts\com.vidjo.idify" /ve /t REG_SZ /d "%MANIFEST_FIREFOX%" /f

echo Registering Native Messaging Host for Chrome...
REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vidjo.idify" /ve /t REG_SZ /d "%MANIFEST_CHROME%" /f

echo Registering Native Messaging Host for Edge...
REG ADD "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.vidjo.idify" /ve /t REG_SZ /d "%MANIFEST_CHROME%" /f

echo.
echo Installed successfully! You can close this window.
pause
