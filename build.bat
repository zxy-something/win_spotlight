@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Spotlight --icon icon.ico main.py
if errorlevel 1 goto :error
echo.
echo Build concluido: dist\Spotlight.exe
pause
exit /b 0

:error
echo.
echo Falha no build.
pause
exit /b 1
