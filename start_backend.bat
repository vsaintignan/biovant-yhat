@echo off
echo === Bio-Meat Intelligence — Backend ===
echo.

cd /d "%~dp0backend"

echo Instalando dependencias...
python -m pip install -r requirements.txt -q

echo.
echo Entrenando modelo IA (Random Forest)...
python train_model.py

echo.
echo Iniciando servidor en http://localhost:8000
echo Dashboard disponible en http://localhost:8000
echo API docs en http://localhost:8000/docs
echo.
echo Presiona Ctrl+C para detener.
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
