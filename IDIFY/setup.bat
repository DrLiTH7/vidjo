@echo off
setlocal
echo ========================================================
echo         VIDJO - Instalador Automatico de Dependencias
echo ========================================================
echo.

set "DIR=%~dp0"
cd /d "%DIR%"

echo [1/5] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Erro: Python nao encontrado no PATH. Instale o Python 3.9+ e tente novamente.
    pause
    exit /b 1
)
echo Python detectado.
echo.

echo [2/5] Instalando uv (Gerenciador de Pacotes) globalmente...
python -m pip install uv
if %errorlevel% neq 0 (
    echo Erro ao instalar uv.
    pause
    exit /b 1
)
echo.

echo [3/5] Instalando dependencias do projeto (criando venv)...
set UV_PROJECT_ENVIRONMENT=venv
python -m uv sync
if %errorlevel% neq 0 (
    echo Erro ao instalar dependencias do projeto.
    pause
    exit /b 1
)
echo Instalacao concluida!
echo.

echo [4/5] Extraindo FFmpeg para o ambiente virtual...
venv\Scripts\python.exe setup_ffmpeg.py
if %errorlevel% neq 0 (
    echo Erro ao configurar o ffmpeg.
    pause
    exit /b 1
)
echo.

echo ========================================================
echo Tudo pronto! O ambiente esta configurado.
echo O Native Messaging Host sera instalado agora para a extensao.
echo ========================================================
echo.
call install_host.bat

echo.
echo ========================================================
echo SETUP CONCLUIDO COM SUCESSO!
echo ========================================================
