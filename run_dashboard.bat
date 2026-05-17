@echo off
REM ===========================================================================
REM  ar-acc - Levanta el servidor web con el dashboard de inconsistencias
REM  Abre el chat de IA en  http://localhost:8000/
REM  Abre el dashboard en   http://localhost:8000/dashboard
REM ===========================================================================

setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo Creando entorno virtual "venv"...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: instala Python 3.10+ y agregalo al PATH.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

echo Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo   Servidor en marcha:
echo     Chat de IA  ->  http://localhost:8000/
echo     Dashboard   ->  http://localhost:8000/dashboard
echo.
echo   Para cargar datos: python pipelines\import_ddjj_real.py --anio 2023
echo   Demo rapida:       cypher-shell -f dashboard\seed_demo.cypher
echo ====================================================================
echo.

uvicorn api.index:app --host 127.0.0.1 --port 8000

endlocal
