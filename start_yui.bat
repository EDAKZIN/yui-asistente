@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Yui AI Assistant - Inicio Automatico
echo   Arquitectura: Backend (venv) + TTS Microservicio (venv_tts)
echo   El TTS se inicia automaticamente cuando Yui lo necesita
echo ============================================================
echo.

cd /d "%~dp0"

REM Verificar que existe el entorno virtual principal
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] El entorno virtual principal no existe.
    echo Ejecuta: python -m venv venv
    echo Luego: pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
    echo        pip install -r requirements.txt
    pause
    exit /b 1
)

REM Verificar que existe el entorno virtual del TTS
if not exist "tts-service\venv_tts\Scripts\python.exe" (
    echo [ERROR] El entorno virtual del TTS no existe.
    echo Ejecuta: cd tts-service
    echo          py -3.11 -m venv venv_tts
    echo          .\venv_tts\Scripts\pip install -r requirements_tts.txt
    pause
    exit /b 1
)

echo [1/2] Limpiando procesos TTS anteriores...
taskkill /FI "WINDOWTITLE eq TTS Microservice*" /F >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *tts_server*" >nul 2>&1

echo [2/2] Iniciando Yui (Backend + Electron)...
echo        El TTS se iniciara automaticamente cuando sea necesario.
echo.
echo ============================================================
echo   Yui esta iniciando...
echo   Presiona Ctrl+C en esta ventana para cerrar todo
echo ============================================================
echo.

call venv\Scripts\activate
python run_electron.py

echo.
echo [INFO] Cerrando procesos...
REM Limpiar cualquier proceso TTS que haya quedado
taskkill /FI "WINDOWTITLE eq TTS Microservice*" /F >nul 2>&1

echo [INFO] Yui cerrada completamente.
pause
